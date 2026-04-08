from dataclasses import dataclass

@dataclass
class SystemConfig:
    """Full system configuration."""
    # Cameras
    detection_camera_index: int = 0
    recording_camera_index: int = 1
    detection_resolution: tuple[int, int] = (1920, 1080)
    recording_resolution: tuple[int, int] = (1920, 1080)
    detection_fps: int = 30
    recording_fps: int = 30  

    # Hailo-8 model
    hef_path: str = "models/yolov8s.hef"
    hailo_input: str = "rpi"
    hailo_frame_skip: int = 2

    # Servo motor
    servo_channel: int = 0
    servo_min_angle: float = 0.0
    servo_max_angle: float = 180.0
    servo_neutral_angle: float = 90.0

    # FOV cameras
    fov_detection_horizontal: float = 140.0
    fov_recording_horizontal: float = 41.0

    # Mechanical offset (degrees)
    mechanical_offset: float = 0.0

    # Tracking parameters
    proximity_threshold: int = 150
    center_deadzone: int = 2  

    # Ball center weighting
    ball_weight: float = 7.0
    person_weight: float = 1.0

    # Progressive center return (px/frame)
    center_return_speed: float = 0.05

    # Output directory
    output_dir: str = "enregistrements"
    version: str = "1.0"

    # Calibration distortion 
    calibration_matrix_path: str = "camera_matrix.npy"
    calibration_coeffs_path: str = "dist_coeffs.npy"
