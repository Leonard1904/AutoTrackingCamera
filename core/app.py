import time
import cv2
from config import SystemConfig
from hardware.camera import CameraManager, HailoDetector, cleanup_hailo_pipeline
from hardware.servo import ServoController
from core.tracking import TargetSelector, AngleCalculator, SpeedAdapter
from io_utils.recorder import VideoRecorder
from io_utils.display import DisplayManager

class DualCameraTrackingApp:
    def __init__(self, config: SystemConfig):
        self.config = config
        self.camera_manager = CameraManager(config)
        self.detector = HailoDetector(config)
        self.target_selector = TargetSelector(config)
        self.angle_calculator = AngleCalculator(config)
        self.speed_adapter = SpeedAdapter()
        self.servo_controller = ServoController(config)
        self.recorder = VideoRecorder(config)
        self.display = DisplayManager(config)
        self.running = False

    def initialize(self) -> bool:
        print("=" * 70)
        print(f"  Basketball Tracking System v{self.config.version}")
        print("=" * 70)
        print()

        if not self.camera_manager.start_recording_camera(): return False
        if not self.detector.load_model(): return False

        print("  Waiting for Hailo stream dimensions...", end="", flush=True)
        for _ in range(50):
            hw, hh = self.detector.get_stream_size()
            if hw > 0 and hh > 0:
                self.target_selector.frame_width = hw
                self.target_selector.frame_height = hh
                self.angle_calculator.frame_width = hw
                self.angle_calculator.center_x = hw / 2.0
                self.recorder.set_detection_size(hw, hh)
                print(f" {hw}×{hh}")
                break
            time.sleep(0.1)
        else: print(" timeout — default dimensions used")
        print("=" * 70)
        return True

    def run(self):
        self.running = True
        try:
            while self.running:
                detection_frame_raw = self.detector.get_latest_frame_copy()
                if detection_frame_raw is None:
                    time.sleep(0.02)
                    continue

                recording_frame = self.camera_manager.capture_recording_frame()
                detection = self.detector.detect()
                hailo_fps = self.detector.get_hailo_fps()

                target = self.target_selector.select_target(detection)
                angle_info = self.angle_calculator.compute_angle(target.position[0])
                speed = self.speed_adapter.compute_speed(self.servo_controller.get_current_angle(), angle_info.angle, target.priority)
                actual_angle = self.servo_controller.move_to(angle_info.angle, speed)

                if self.recorder.recording:
                    metadata = {
                        "target_cx": target.position, "target_cy": target.position,
                        "target_mode": target.mode, "target_priority": f"{target.priority:.2f}",
                        "servo_angle": f"{actual_angle:.2f}", "servo_direction": angle_info.direction,
                        "error_px": angle_info.error_px, "error_degrees": f"{angle_info.error_degrees:.2f}",
                        "servo_speed": f"{speed:.2f}", "fps": f"{hailo_fps:.2f}",
                        "nb_persons": len(detection.person_centers), "nb_balls": 1 if detection.ball_center else 0,
                    }
                    self.recorder.write_frame(recording_frame=recording_frame, detection_frame=detection_frame_raw, metadata=metadata)

                detection_frame_display = detection_frame_raw.copy()
                self.display.draw_detections(detection_frame_display, detection)
                self.display.draw_target(detection_frame_display, target)
                self.display.draw_overlay(detection_frame_display, hailo_fps, {"angle": actual_angle, "direction": angle_info.direction, "speed": speed}, self.recorder)

                self.display.show_detection(detection_frame_display)
                self.display.show_recording(recording_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord(" "):
                    if not self.recorder.recording: self.recorder.start()
                    elif self.recorder.paused: self.recorder.resume()
                    else: self.recorder.pause()
                elif key == 27:
                    if self.recorder.recording: self.recorder.stop()
                elif key in (ord("b"), ord("B")): self.display.show_boxes = not self.display.show_boxes
                elif key in (ord("t"), ord("T")): self.display.show_target = not self.display.show_target
                elif key in (ord("q"), ord("Q")): break
        except KeyboardInterrupt: print("\n  Keyboard interruption")
        finally: self.cleanup()

    def cleanup(self):
        print("\n  Cleaning up...")
        if self.recorder.recording: self.recorder.stop()
        self.servo_controller.reset_to_neutral()
        cleanup_hailo_pipeline()
        self.camera_manager.stop_all()
        self.display.destroy()
        print(" Done\n")
