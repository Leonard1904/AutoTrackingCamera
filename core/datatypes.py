from dataclasses import dataclass
from typing import Optional

@dataclass
class DetectionResult:
    """Hailo detection result."""
    person_centers: list[tuple[int, int]]
    ball_center: Optional[tuple[int, int]]
    hailo_boxes: list[tuple[int, int, int, int, str, float]]

@dataclass
class TargetInfo:
    """Information about the target to follow."""
    position: tuple[int, int]
    mode: str
    priority: float

@dataclass
class AngleInfo:
    """Information about the servo angle calculated."""
    angle: float
    direction: str
    error_px: float
    error_degrees: float