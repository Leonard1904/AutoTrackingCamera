import math
from config import SystemConfig
from core.datatypes import DetectionResult, TargetInfo, AngleInfo

# DBSCAN

def _dbscan(points: list[tuple[int, int]], eps: float, min_pts: int) -> list[int]:

    n = len(points)
    labels = [-2] * n  

    def neighbors(i: int) -> list[int]:
        return [
            j for j in range(n)
            if math.hypot(points[i][0] - points[j][0],
                          points[i][1] - points[j][1]) <= eps
        ]

    cluster_id = 0
    for i in range(n):
        if labels[i] != -2:
            continue
        nb = neighbors(i)
        if len(nb) < min_pts:
            labels[i] = -1
            continue
        labels[i] = cluster_id
        seed = set(nb) - {i}
        while seed:
            j = seed.pop()
            if labels[j] == -1:
                labels[j] = cluster_id
            if labels[j] != -2:
                continue
            labels[j] = cluster_id
            nb_j = neighbors(j)
            if len(nb_j) >= min_pts:
                seed.update(nb_j)
        cluster_id += 1

    for i in range(n):
        if labels[i] == -2:
            labels[i] = -1
    return labels


#  TARGET SELECTOR

class TargetSelector:

    def __init__(self, config: SystemConfig):
        self.config = config
        w, h = config.detection_resolution
        self.frame_width  = float(w)
        self.frame_height = float(h)

        self._last_target: tuple[float, float] = (
            self.frame_width  / 2.0,
            self.frame_height / 2.0,
        )

        self._smooth_alpha: float = 0.3
        self._smoothed_target: tuple[float, float] = (
            self.frame_width  / 2.0,
            self.frame_height / 2.0,
        )

        self._dbscan_eps: float = 100.0
        self._dbscan_min_pts: int = 1

    def _apply_smooth(self, raw_x: float, raw_y: float) -> tuple[int, int]:
        sx = self._smoothed_target[0] + self._smooth_alpha * (raw_x - self._smoothed_target[0])
        sy = self._smoothed_target[1] + self._smooth_alpha * (raw_y - self._smoothed_target[1])
        self._smoothed_target = (sx, sy)
        return (int(sx), int(sy))

    def _retour_centre(self) -> tuple[int, int]:
        cx = self.frame_width  / 2.0
        cy = self.frame_height / 2.0
        lx, ly = self._last_target
        s  = self.config.center_return_speed
        rx = lx + s * (cx - lx)
        ry = ly + s * (cy - ly)
        self._last_target = (rx, ry)
        return self._apply_smooth(rx, ry)

    def select_target(self, detection: DetectionResult) -> TargetInfo:

        # Barycenter Logic
        
        ball_total   = self.config.ball_weight if detection.ball_center else 0.0
        person_total = self.config.person_weight * len(detection.person_centers)

        if ball_total == 0.0 and person_total == 0.0:
            pos = self._retour_centre()
            return TargetInfo(position=pos, mode="RETOUR_AU_CENTRE", priority=0.0)

        if detection.ball_center and ball_total >= person_total:
            bx, by = detection.ball_center
            self._last_target = (float(bx), float(by))
            priority = min(1.0, ball_total / (self.config.ball_weight + 2))
            pos = self._apply_smooth(float(bx), float(by))
            return TargetInfo(position=pos, mode="BALLON_PRIORITAIRE", priority=priority)

        xs = [px for px, _ in detection.person_centers]
        ys = [py for _, py in detection.person_centers]
        if not xs:
            cx, cy = self.frame_width / 2.0, self.frame_height / 2.0
        else:
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
        self._last_target = (cx, cy)
        priority = min(1.0, person_total / (self.config.ball_weight + 2))
        pos = self._apply_smooth(cx, cy)
        return TargetInfo(position=pos, mode="GROUPE_JOUEURS", priority=priority)
        
        # END OF BARYCENTER 

        # # DBSCAN Logic ======= Uncomment this section up to the end of DBSCAN and comment out the other one (BARYCENTRE) to use this logic
            
        # ball_confidence = 1.0  
        # has_ball    = detection.ball_center is not None
        # has_players = len(detection.person_centers) > 0

        # if not has_ball and not has_players:
        #     pos = self._retour_centre()
        #     return TargetInfo(position=pos, mode="RETOUR_AU_CENTRE", priority=0.0)

        # all_points: list[tuple[int, int]] = list(detection.person_centers)
        # ball_indices: set[int] = set()

        # if has_ball:
        #     n_copies = max(1, round(self.config.ball_weight * ball_confidence))
        #     for _ in range(n_copies):
        #         ball_indices.add(len(all_points))
        #         all_points.append(detection.ball_center)

        # effective_min_pts = min(self._dbscan_min_pts, len(all_points))
        # labels = _dbscan(all_points, eps=self._dbscan_eps,
        #                  min_pts=effective_min_pts)

        # groups: dict[int, dict] = {}
        # for idx, (pt, lbl) in enumerate(zip(all_points, labels)):
        #     if lbl not in groups:
        #         groups[lbl] = {"players": [], "ball_copies": 0}
        #     if idx in ball_indices:
        #         groups[lbl]["ball_copies"] += 1
        #     else:
        #         groups[lbl]["players"].append(pt)

        # best_label    = None
        # best_weight   = -1.0
        # best_players  = []
        # best_has_ball = False
        # best_ball_cop = 0

        # for lbl, data in groups.items():
        #     players   = data["players"]
        #     ball_cop  = data["ball_copies"]
        #     # Total weight = players × player_weight + balls × ball_weight × confidence
        #     w_players = len(players) * self.config.person_weight
        #     w_ball    = ball_cop * self.config.ball_weight * ball_confidence
        #     total_w   = w_players + w_ball
        #     if total_w > best_weight:
        #         best_weight   = total_w
        #         best_label    = lbl
        #         best_players  = players
        #         best_has_ball = ball_cop > 0
        #         best_ball_cop = ball_cop

        # if best_label is None:
        #     pos = self._retour_centre()
        #     return TargetInfo(position=pos, mode="RETOUR_AU_CENTRE", priority=0.0)

        # total_weight = 0.0
        # wx = 0.0
        # wy = 0.0

        # for px, py in best_players:
        #     w   = self.config.person_weight
        #     wx += px * w
        #     wy += py * w
        #     total_weight += w

        # if best_has_ball and detection.ball_center is not None:
        #     bx, by  = detection.ball_center
        #     w_ball  = self.config.ball_weight * ball_confidence
        #     wx     += bx * w_ball
        #     wy     += by * w_ball
        #     total_weight += w_ball

        # if total_weight > 0:
        #     raw_x = wx / total_weight
        #     raw_y = wy / total_weight
        # else:
        #     raw_x = self.frame_width  / 2.0
        #     raw_y = self.frame_height / 2.0

        # self._last_target = (raw_x, raw_y)

        # pos = self._apply_smooth(raw_x, raw_y)

        # total_players = len(detection.person_centers)
        # if best_has_ball:
        #     mode = f"DBSCAN_BALLON_{len(best_players)}J/{total_players}J"
        # else:
        #     mode = f"DBSCAN_{len(best_players)}J/{total_players}J"

        # priority = min(1.0, best_weight / max(
        #     self.config.ball_weight + total_players * self.config.person_weight, 1
        # ))
        # return TargetInfo(position=pos, mode=mode, priority=priority)

        # # END OF DBSCAN

#  ANGLE CALCULATOR

class AngleCalculator:

    def __init__(self, config: SystemConfig):
        self.config = config

        w, _ = config.detection_resolution
        self.frame_width_val = float(w)
        self.center_x        = self.frame_width_val / 2.0
        self.neutral_angle   = config.servo_neutral_angle

        fov_rad    = math.radians(config.fov_detection_horizontal)
        self.f_det = self.center_x / math.tan(fov_rad / 2.0)

        self._prev_error_px:      float = 0.0
        self._smoothed_alpha_deg: float = 0.0
        self._alpha_smooth:       float = 0.6
        self._angle_deadzone_deg: float = 2.0

    def compute_angle(self, target_x: int) -> AngleInfo:
        error_px = self.center_x - float(target_x)

        if abs(error_px) < self.config.center_deadzone:
            self._prev_error_px       = error_px
            self._smoothed_alpha_deg *= (1.0 - self._alpha_smooth)
            return AngleInfo(
                angle=self.neutral_angle + self.config.mechanical_offset,
                direction="CENTRE",
                error_px=error_px,
                error_degrees=0.0,
            )

        # Adaptive gain
        # Reduced to 0.7 when the target approaches the center AND is within the
        # central 15% of the image. Prevents overshoot.
        error_decreasing = abs(error_px) < abs(self._prev_error_px)
        adaptive_gain    = (0.7 if (error_decreasing and
                                    abs(error_px) < self.frame_width_val * 0.15)
                            else 1.0)

        alpha_raw = math.degrees(math.atan((error_px * adaptive_gain) / self.f_det))

        self._smoothed_alpha_deg = (
            self._alpha_smooth       * alpha_raw
            + (1.0 - self._alpha_smooth) * self._smoothed_alpha_deg
        )

        # Angular deadzone 
        # If the smoothed angle is too small (residual noise), it is forced to 0:
        # the servo remains stationary rather than oscillating within +/-2°.
        if abs(self._smoothed_alpha_deg) < self._angle_deadzone_deg:
            self._smoothed_alpha_deg = 0.0

        angle = max(
            self.config.servo_min_angle,
            min(
                self.config.servo_max_angle,
                self.neutral_angle - self._smoothed_alpha_deg
                + self.config.mechanical_offset,
            ),
        )

        self._prev_error_px = error_px

        direction = ("CENTRE" if abs(error_px) <= self.config.center_deadzone
                     else "GAUCHE" if error_px > 0 else "DROITE")

        return AngleInfo(
            angle=angle,
            direction=direction,
            error_px=error_px,
            error_degrees=self._smoothed_alpha_deg,
        )

#  SPEED ADAPTER

class SpeedAdapter:

    def __init__(self):
        self.last_speed          = 0.0
        self.speed_smooth_factor = 0.15   
        self.min_speed           = 0.15   
        self.max_speed           = 0.8   
        self.max_error_deg       = 40.0   

    def compute_speed(self, current_angle: float, target_angle: float,
                      priority: float) -> float:
        error_degrees = abs(target_angle - current_angle)

        normalized_error = min(error_degrees / self.max_error_deg, 1.0)

        base_speed = self.min_speed + (normalized_error ** 1.5) * (
            self.max_speed - self.min_speed
        )

        adjusted_speed = base_speed * (0.5 + priority * 0.5)

        smooth_speed = self.last_speed + self.speed_smooth_factor * (
            adjusted_speed - self.last_speed
        )
        smooth_speed    = max(self.min_speed, min(self.max_speed, smooth_speed))
        self.last_speed = smooth_speed
        return smooth_speed
