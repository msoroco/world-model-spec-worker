"""Native right-indicator requests from measured remaining approach distance.

Requested boundaries are engineering targets. Original state and path samples,
not this schedule, determine the final observed statutory distance.
"""

import math

from turn_signal_control import set_right_indicator


FEET_TO_M = 0.3048
CASE_TARGET_FEET = {
    "right_business_under_100_ft": 99,
    "right_business_at_100_ft": 100,
    "right_business_over_100_ft": 101,
    "right_residential_at_100_ft": 100,
    "right_other_under_300_ft": 299,
    "right_other_at_300_ft": 300,
    "right_other_over_300_ft": 301,
    "right_interrupted": 100,
}


def remaining_approach_m(points, xy, *, max_lateral_m=3):
    if len(points) < 3 or len(xy) != 2:
        raise ValueError("Complete source route and position required")
    points = [tuple(map(float, point)) for point in points]
    xy = tuple(map(float, xy))
    if any(len(point) != 2 or any(not math.isfinite(v) for v in point) for point in points + [xy]):
        raise ValueError("Finite source route coordinates required")
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    if any(length <= 0 or length > 5 for length in lengths):
        raise ValueError("Contiguous approach centerline required")
    total = sum(lengths)
    if total < 91.44:
        raise ValueError("Approach too short for 300-foot alternative")
    candidates = []
    traveled = 0.0
    for a, b, length in zip(points, points[1:], lengths):
        vx, vy = b[0] - a[0], b[1] - a[1]
        along = max(0.0, min(1.0, ((xy[0] - a[0]) * vx + (xy[1] - a[1]) * vy) / length**2))
        projected = (a[0] + along * vx, a[1] + along * vy)
        candidates.append((math.dist(xy, projected), total - traveled - along * length))
        traveled += length
    lateral, remaining = min(candidates)
    if lateral > max_lateral_m:
        raise ValueError("Vehicle departed source approach")
    return remaining


class DistanceController:
    def __init__(self, case_name, approach_points_xy_m):
        if case_name not in CASE_TARGET_FEET:
            raise ValueError("Unsupported right-turn signal case")
        self.case_name = case_name
        self.target_m = CASE_TARGET_FEET[case_name] * FEET_TO_M
        self.points = approach_points_xy_m
        self.previous_remaining = None
        self.saw_initial_off = False

    def step(self, actor, light_state_type):
        position = actor.get_location()
        remaining = remaining_approach_m(self.points, (position.x, position.y))
        if self.previous_remaining is not None and remaining > self.previous_remaining + 0.25:
            raise ValueError("Vehicle reversed on source approach")
        self.previous_remaining = remaining
        enabled = remaining <= self.target_m + 1e-6
        if self.case_name == "right_interrupted" and 14 <= remaining <= 16:
            enabled = False
        if not enabled:
            self.saw_initial_off = True
        if enabled and not self.saw_initial_off:
            raise ValueError("No observed Off-to-On request before turn")
        result = set_right_indicator(actor, light_state_type, enabled)
        if result["readback_right_indicator"] != enabled:
            raise ValueError("Native right-indicator request/readback differs")
        return {"remaining_approach_m": remaining,
                "requested_right_indicator": enabled,
                "readback_right_indicator": result["readback_right_indicator"],
                "statutory_distance_claimed": False}
