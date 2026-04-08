from config import SystemConfig

try:
    from adafruit_servokit import ServoKit
    SERVO_AVAILABLE = True
except ImportError:
    SERVO_AVAILABLE = False

class ServoController:
    """Control the servo motor with smoothing."""

    def __init__(self, config: SystemConfig):
        self.config = config
        self.current_angle = config.servo_neutral_angle
        self.kit = None

        if SERVO_AVAILABLE:
            try:
                self.kit = ServoKit(channels=16)
                self.kit.servo[config.servo_channel].angle = int(self.current_angle)
                print(f"  Servo initialized to {self.current_angle}°")
            except Exception as e:
                print(f"  Servo simulation : {e}")
        else:
            print("  Servo in simulation mode")

    def move_to(self, target_angle: float, speed: float) -> float:
        smooth_angle = max(
            self.config.servo_min_angle,
            min(
                self.config.servo_max_angle,
                self.current_angle + speed * (target_angle - self.current_angle),
            ),
        )
        if self.kit is not None:
            try:
                self.kit.servo[self.config.servo_channel].angle = int(smooth_angle)
            except Exception as e:
                print(f"  Servo error : {e}")
        self.current_angle = smooth_angle
        return smooth_angle

    def get_current_angle(self) -> float:
        return self.current_angle

    def reset_to_neutral(self):
        self.move_to(self.config.servo_neutral_angle, 0.5)