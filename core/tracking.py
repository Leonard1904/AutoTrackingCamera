import math
from config import SystemConfig
from core.datatypes import DetectionResult, TargetInfo, AngleInfo

class TargetSelector:
    def __init__(self, config: SystemConfig):
        self.config = config
        
        w, h = config.detection_resolution
        
        self.frame_width = float(w)
        self.frame_height = float(h)
        
        self._last_target: tuple[float, float] = (
            self.frame_width / 2.0,
            self.frame_height / 2.0,
        )

    def select_target(self, detection: DetectionResult) -> TargetInfo:
        ball_total = self.config.ball_weight if detection.ball_center else 0.0
        person_total = self.config.person_weight * len(detection.person_centers)

        if ball_total == 0.0 and person_total == 0.0:
            center_x = self.frame_width  / 2.0
            center_y = self.frame_height / 2.0
            lx, ly = self._last_target
            s = self.config.center_return_speed
            cx = lx + s * (center_x - lx)
            cy = ly + s * (center_y - ly)
            self._last_target = (cx, cy)
            return TargetInfo(position=(int(cx), int(cy)), mode="CENTER_RETURN", priority=0.0)

        if detection.ball_center and ball_total >= person_total:
            bx, by = detection.ball_center
            self._last_target = (float(bx), float(by))
            priority = min(1.0, ball_total / (self.config.ball_weight + 2))
            return TargetInfo(position=(bx, by), mode="BALL_PRIORITY", priority=priority)

        xs = [px for px, _ in detection.person_centers]
        ys = [py for _, py in detection.person_centers]
        
        if not xs:
            cx, cy = int(self.frame_width/2), int(self.frame_height/2)
        else:
            cx = int(sum(xs) / len(xs))
            cy = int(sum(ys) / len(ys))
            
        self._last_target = (float(cx), float(cy))
        priority = min(1.0, person_total / (self.config.ball_weight + 2))
        return TargetInfo(position=(cx, cy), mode="GROUP_PLAYERS", priority=priority)


class AngleCalculator:
    """Calculate the servo angle to center the recording camera on the target."""

    def __init__(self, config: SystemConfig):
        self.config = config
        
        w, _ = config.detection_resolution  
        self.frame_width_val = float(w)
        
        self.center_x = self.frame_width_val / 2.0
        self.neutral_angle = config.servo_neutral_angle
        
        fov_rad = math.radians(config.fov_detection_horizontal)
        self.f_det = self.center_x / math.tan(fov_rad / 2.0)

    def compute_angle(self, target_x: int) -> AngleInfo:
        error_px = self.center_x - float(target_x)
        
        alpha_deg = math.degrees(math.atan(error_px / self.f_det))
        
        angle = max(
            self.config.servo_min_angle,
            min(
                self.config.servo_max_angle,
                self.neutral_angle - alpha_deg + self.config.mechanical_offset,
            ),
        )

        if abs(error_px) <= self.config.center_deadzone:
            direction = "CENTER"
        elif error_px > 0:
            direction = "LEFT"
        else:
            direction = "RIGHT"

        return AngleInfo(
            angle=angle, 
            direction=direction, 
            error_px=error_px, 
            error_degrees=alpha_deg
        )


class SpeedAdapter:
    """Calculate the adaptive servo speed with a smooth mathematical curve."""

    def __init__(self):
        self.last_speed = 0.0
        self.speed_smooth_factor = 0.15
        self.min_speed = 0.02
        self.max_speed = 1.0
        self.max_error_deg = 40.0

    def compute_speed(self, current_angle: float, target_angle: float, priority: float) -> float:
        error_degrees = abs(target_angle - current_angle)
        normalized_error = min(error_degrees / self.max_error_deg, 1.0)
        base_speed = self.min_speed + (normalized_error ** 1.5) * (self.max_speed - self.min_speed)
        adjusted_speed = base_speed * (0.5 + priority * 0.5)
        smooth_speed = self.last_speed + self.speed_smooth_factor * (adjusted_speed - self.last_speed)
        smooth_speed = max(self.min_speed, min(self.max_speed, smooth_speed))
        self.last_speed = smooth_speed
        return smooth_speed
