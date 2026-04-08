import os
import time
import math
import subprocess
import threading
import atexit
from pathlib import Path
from typing import Optional
import numpy as np
import cv2

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

import hailo
from hailo_apps.hailo_app_python.core.common.core import get_default_parser
from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import GStreamerDetectionApp

from picamera2 import Picamera2

from config import SystemConfig
from core.datatypes import DetectionResult

class CameraManager:
    """Manage the recording camera (Picamera2)."""

    def __init__(self, config: SystemConfig):
        self.config = config
        self.recording_cam = None
        self.camera_matrix = None
        self.dist_coeffs = None

    def start_recording_camera(self) -> bool:
        print(" Loading calibration parameters...")
        try:
            self.camera_matrix = np.load(self.config.calibration_matrix_path)
            self.dist_coeffs = np.load(self.config.calibration_coeffs_path)
            print(" Calibration loaded - distortion correction enabled")
        except Exception:
            self.camera_matrix = None
            self.dist_coeffs = None
            print(" Calibration files not found - distortion not corrected")

        print(f"  Recording camera initialization (index {self.config.recording_camera_index})...")
        try:
            self.recording_cam = Picamera2(self.config.recording_camera_index)
            cam_config = self.recording_cam.create_preview_configuration(
                main={"size": self.config.recording_resolution, "format": "RGB888"},
                controls={"FrameRate": self.config.recording_fps}
            )
            self.recording_cam.configure(cam_config)
            self.recording_cam.start()
            time.sleep(1.0)
            print("  Recording camera ready")
            return True
        except Exception as e:
            print(f"  Recording camera error : {e}")
            return False

    def capture_recording_frame(self) -> Optional[np.ndarray]:
        if self.recording_cam:
            return self.recording_cam.capture_array()
        return None

    def stop_all(self):
        if self.recording_cam:
            self.recording_cam.stop()
            self.recording_cam.close()


# --- HAILO GLOBALS & CALLBACKS ---
_hailo_lock = threading.Lock()
_hailo_person_centers: list[tuple[int, int]] = []
_hailo_ball_center: Optional[tuple[int, int]] = None
_hailo_boxes: list[tuple[int, int, int, int, str, float]] = []
_hailo_stream_w: int = 0
_hailo_stream_h: int = 0
_hailo_app: Optional[GStreamerDetectionApp] = None
_hailo_pipeline_thread: Optional[threading.Thread] = None

_hailo_fps: float = 0.0
_hailo_fps_counter: int = 0
_hailo_fps_timer: float = time.time()
_hailo_latest_frame: Optional[np.ndarray] = None

_hailo_cleanup_done = False
_hailo_cleanup_lock = threading.Lock()

def cleanup_hailo_pipeline() -> None:
    global _hailo_app, _hailo_pipeline_thread, _hailo_cleanup_done
    with _hailo_cleanup_lock:
        if _hailo_cleanup_done: return
        _hailo_cleanup_done = True
    app = _hailo_app
    _hailo_app = None
    if app is not None:
        try:
            if hasattr(app, "pipeline") and app.pipeline is not None:
                app.pipeline.set_state(Gst.State.NULL)
            if hasattr(app, "loop") and app.loop is not None and app.loop.is_running():
                app.loop.quit()
        except Exception: pass
    thread = _hailo_pipeline_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=3.0)
    time.sleep(0.3)

atexit.register(cleanup_hailo_pipeline)

def _force_restart_hailo_driver() -> bool:
    print("  Restarting Hailo driver...")
    try:
        subprocess.run(["sudo", "pkill", "-f", "gst-launch"], timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        result = subprocess.run(["lsmod"], capture_output=True, text=True)
        if "hailo" in result.stdout:
            subprocess.run(["sudo", "rmmod", "hailo"], timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
        subprocess.run(["sudo", "modprobe", "hailo"], timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
    except Exception as e:
        print(f"  Warning Hailo restart : {e}")
    return os.path.exists("/dev/hailo0")

def ensure_hailo_ready() -> bool:
    print("  Checking Hailo-8...")
    if not os.path.exists("/dev/hailo0"):
        print("  /dev/hailo0 absent — restart driver attempt...")
        if not _force_restart_hailo_driver():
            return False
    time.sleep(1)
    print("  Hailo-8 ready")
    return True

class _HailoUserData(app_callback_class):
    def __init__(self, frame_skip: int):
        super().__init__()
        self.frame_skip = max(1, frame_skip)
        self._count = 0
    def increment(self): self._count += 1
    def get_count(self): return self._count

def _hailo_callback(pad, info, user_data: _HailoUserData):
    global _hailo_stream_w, _hailo_stream_h, _hailo_fps, _hailo_fps_counter, _hailo_fps_timer
    user_data.increment()
    _hailo_fps_counter += 1
    now = time.time()
    elapsed = now - _hailo_fps_timer
    if elapsed >= 1.0:
        with _hailo_lock: _hailo_fps = _hailo_fps_counter / elapsed
        _hailo_fps_counter = 0
        _hailo_fps_timer = now

    if user_data.get_count() % user_data.frame_skip != 0: return Gst.PadProbeReturn.OK

    buffer = info.get_buffer()
    if buffer is None: return Gst.PadProbeReturn.OK

    fmt, width, height = get_caps_from_pad(pad)
    if width is None or height is None: return Gst.PadProbeReturn.OK

    _hailo_stream_w, _hailo_stream_h = int(width), int(height)
    frame = get_numpy_from_buffer(buffer, fmt, width, height) if user_data.use_frame and fmt else None

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    person_centers, boxes, ball_center = [], [], None
    w, h = int(width), int(height)
    for det in detections:
        label = det.get_label()
        if label not in ("person", "sports ball"): continue
        bbox = det.get_bbox()
        conf = float(det.get_confidence())
        x1, y1 = int(bbox.xmin() * w), int(bbox.ymin() * h)
        x2, y2 = int(bbox.xmax() * w), int(bbox.ymax() * h)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        boxes.append((x1, y1, x2, y2, label, conf))
        if label == "person": person_centers.append((cx, cy))
        else: ball_center = (cx, cy)

    latest = cv2.cvtColor(np.copy(frame), cv2.COLOR_RGB2BGR) if frame is not None else None

    with _hailo_lock:
        global _hailo_person_centers, _hailo_ball_center, _hailo_boxes, _hailo_latest_frame
        _hailo_person_centers = person_centers
        _hailo_ball_center = ball_center
        _hailo_boxes = boxes
        if latest is not None: _hailo_latest_frame = latest

    return Gst.PadProbeReturn.OK

class HailoDetector:
    def __init__(self, config: SystemConfig):
        self.config = config
        self.user_data: Optional[_HailoUserData] = None

    def load_model(self) -> bool:
        global _hailo_app, _hailo_pipeline_thread
        if not ensure_hailo_ready(): return False
        
        hef = Path(self.config.hef_path).resolve()
        if not hef.is_file():
            print(f"  .hef file not found : {hef}")
            return False

        Gst.init(None)
        self.user_data = _HailoUserData(self.config.hailo_frame_skip)
        self.user_data.use_frame = True

        parser = get_default_parser()
        parser.set_defaults(input=self.config.hailo_input, hef_path=str(hef), use_frame=True, show_fps=False, disable_overlay=True)
        parser.parse_args([])

        try:
            _hailo_app = GStreamerDetectionApp(_hailo_callback, self.user_data, parser)
        except Exception as e:
            print(f"  Hailo pipeline creation error : {e}")
            return False

        def _run():
            try: _hailo_app.run()
            except Exception as ex: print(f"  Hailo pipeline stopped : {ex}")

        _hailo_pipeline_thread = threading.Thread(target=_run, daemon=True)
        _hailo_pipeline_thread.start()
        time.sleep(2.0)
        print(f"  Hailo pipeline started — {hef.name}")
        return True

    def detect(self) -> DetectionResult:
        with _hailo_lock:
            return DetectionResult(list(_hailo_person_centers), _hailo_ball_center, list(_hailo_boxes))

    def get_latest_frame_copy(self) -> Optional[np.ndarray]:
        with _hailo_lock:
            return np.copy(_hailo_latest_frame) if _hailo_latest_frame is not None else None

    def get_stream_size(self) -> tuple[int, int]:
        with _hailo_lock:
            return _hailo_stream_w, _hailo_stream_h

    def get_hailo_fps(self) -> float:
        with _hailo_lock:
            return _hailo_fps