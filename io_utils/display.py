import cv2
import time
import numpy as np
from typing import Optional
from config import SystemConfig
from core.datatypes import DetectionResult, TargetInfo
from io_utils.recorder import VideoRecorder

class DisplayManager:
    def __init__(self, config: SystemConfig):
        self.config = config
        self.window_detection = "Camera 0 - Detection"
        self.window_recording = "Camera 1 - Recording"
        self.show_boxes = True
        self.show_target = True

        cv2.namedWindow(self.window_detection, cv2.WINDOW_NORMAL)
        cv2.namedWindow(self.window_recording, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_detection, 1280, 720)
        cv2.resizeWindow(self.window_recording, 1280, 720)

    def draw_detections(self, frame: np.ndarray, detection: DetectionResult):
        if not self.show_boxes: return
        for x1, y1, x2, y2, label, conf in detection.hailo_boxes:
            color = (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
            cv2.putText(frame, f"{label} {conf * 100:.0f}%", (x1, max(y1 - 8, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def draw_target(self, frame: np.ndarray, target: TargetInfo):
        if not self.show_target: return
        cx, cy = target.position
        if target.priority >= 0.9: color = (0, 0, 255)
        elif target.priority >= 0.7: color = (0, 165, 255)
        else: color = (0, 255, 255)
        cv2.circle(frame, (cx, cy), 12, color, 3)
        cv2.putText(frame, target.mode, (cx + 15, cy - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def draw_overlay(self, frame: np.ndarray, fps: float, servo_info: dict, recorder: VideoRecorder):
        h, _ = frame.shape[:2]
        bg = frame.copy()
        cv2.rectangle(bg, (10, 55), (410, 250), (0, 0, 0), -1)
        cv2.addWeighted(bg, 0.55, frame, 0.45, 0, frame)

        cv2.putText(frame, f"FPS : {fps:.1f}", (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Servo : {servo_info.get('angle', 90):.1f} {servo_info.get('direction', '')}", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"Speed : {servo_info.get('speed', 0):.2f}", (20, 152), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        if not recorder.recording: status, col = "READY", (0, 255, 0)
        elif recorder.paused: status, col = "PAUSE", (0, 165, 255)
        else: status, col = "REC", (0, 0, 255)

        dur = f" {recorder.get_duration() // 60:02d}:{recorder.get_duration() % 60:02d}" if recorder.recording else ""
        cv2.putText(frame, f"{status}{dur}", (280, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
        if recorder.recording and not recorder.paused and int(time.time() * 2) % 2: cv2.circle(frame, (395, 114), 8, col, -1)
        cv2.putText(frame, "SPC:Rec  ESC:Stop  B:Boxes  T:Target  Q:Quit", (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    def show_detection(self, frame: np.ndarray): cv2.imshow(self.window_detection, frame)
    def show_recording(self, recording_frame: Optional[np.ndarray]):
        if recording_frame is not None: cv2.imshow(self.window_recording, recording_frame)
    def destroy(self): cv2.destroyAllWindows()
