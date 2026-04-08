import queue
import threading
import cv2
import os
import csv
import time
import numpy as np
from datetime import datetime
from typing import Optional
from config import SystemConfig

class VideoRecorder:
    def __init__(self, config: SystemConfig):
        self.config = config
        self.writer_rec = None          
        self.csv_file = None
        self.csv_writer = None
        self.recording = False
        self.paused = False
        
        self.frame_count = 0
        self.video_id = None
        self.start_time = None
        self.pause_time = None
        self.paused_duration = 0
        self._det_actual_size = config.detection_resolution
        
        self.frame_queue = queue.Queue(maxsize=120) 
        self.write_thread = None
        os.makedirs(config.output_dir, exist_ok=True)

    def set_detection_size(self, w: int, h: int) -> None:
        if w > 0 and h > 0: self._det_actual_size = (w, h)

    def start(self) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.video_id = f"recording_{ts}"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        path_rec = os.path.join(self.config.output_dir, f"{self.video_id}_cam1_recording.mp4")
        
        self.writer_rec = cv2.VideoWriter(path_rec, fourcc, self.config.recording_fps, self.config.recording_resolution)
        
        csv_path = os.path.join(self.config.output_dir, f"{self.video_id}.csv")
        self.csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            "video_id", "frame_num", "timestamp", "target_cx", "target_cy", "target_mode", "target_priority",
            "servo_angle", "servo_direction", "error_px", "error_degrees", "servo_speed", "fps", "nb_persons", "nb_balls"
        ])

        self.recording = True
        self.paused = False
        self.frame_count = 0
        self.start_time = time.time()
        self.paused_duration = 0

        self.write_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self.write_thread.start()
        print(f"   Recording started : {path_rec}")
        return path_rec

    def _writer_loop(self):
        while self.recording or not self.frame_queue.empty():
            try:
                item = self.frame_queue.get(timeout=0.1)
                rec_frame, metadata, count = item
                if rec_frame is not None and self.writer_rec is not None:
                    self.writer_rec.write(rec_frame)

                if self.csv_writer:
                    self.csv_writer.writerow([
                        self.video_id, count, datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        metadata.get("target_cx", ""), metadata.get("target_cy", ""), metadata.get("target_mode", ""),
                        metadata.get("target_priority", ""), metadata.get("servo_angle", ""), metadata.get("servo_direction", ""),
                        metadata.get("error_px", ""), metadata.get("error_degrees", ""), metadata.get("servo_speed", ""),
                        metadata.get("fps", ""), metadata.get("nb_persons", 0), metadata.get("nb_balls", 0),
                    ])
                self.frame_queue.task_done()
            except queue.Empty: continue
            except Exception as e: print(f"Video writing error : {e}")

    def write_frame(self, recording_frame: Optional[np.ndarray], detection_frame: Optional[np.ndarray], metadata: dict) -> None:
        if not self.recording or self.paused: return
        self.frame_count += 1
        rec_frame_copy = np.copy(recording_frame) if recording_frame is not None else None
        try: self.frame_queue.put_nowait((rec_frame_copy, metadata, self.frame_count))
        except queue.Full: pass

    def pause(self):
        if self.recording and not self.paused:
            self.paused = True
            self.pause_time = time.time()
            print("  Recording paused")

    def resume(self):
        if self.recording and self.paused:
            self.paused_duration += time.time() - self.pause_time
            self.pause_time = None
            self.paused = False
            print("  Recording resumed")

    def stop(self):
        if not self.recording: return
        print("  Stopping, waiting for writing...")
        self.recording = False
        if self.write_thread is not None: self.write_thread.join(timeout=2.0)
        if self.writer_rec is not None: self.writer_rec.release(); self.writer_rec = None
        if self.csv_file is not None: self.csv_file.close(); self.csv_file = None
        print(f"  Recording stopped : {self.frame_count} frames recorded")

    def get_duration(self) -> int:
        if not self.start_time: return 0
        total = time.time() - self.start_time - self.paused_duration
        if self.paused and self.pause_time: total -= time.time() - self.pause_time
        return max(0, int(total))