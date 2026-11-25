"""Deterministic approach targets; original Native readback decides completion."""
from branch_variants import BRANCHES


def approach_command(suffix, center_x_m, speed_mps):
    branch = BRANCHES[suffix]
    if branch.side == "same":
        remaining = branch.target_center_x_m - center_x_m
        direction = 1
    else:
        remaining = center_x_m - branch.target_center_x_m
        direction = -1
    if remaining <= 0.5:
        return {"target_velocity_x_mps": 0.0, "brake": 1.0,
                "phase": "rest_target", "activity": branch.activity,
                "exception": branch.exception}
    desired = min(4.0, max(0.5, remaining * 0.4))
    if speed_mps > desired + 0.5:
        return {"target_velocity_x_mps": direction * desired, "brake": 0.5,
                "phase": "decelerating", "activity": branch.activity,
                "exception": branch.exception}
    return {"target_velocity_x_mps": direction * desired, "brake": 0.0,
            "phase": "approaching", "activity": branch.activity,
            "exception": branch.exception}


def completion_observation(rows, suffix):
    """Require a sustained original readback, retaining legal interpretation."""
    branch = BRANCHES[suffix]
    if len(rows) < 40:
        raise ValueError("At least two seconds of original 20 Hz rest evidence required")
    tail = rows[-40:]
    for row in tail:
        center = row.get("center_xy_m")
        speed = row.get("speed_mps")
        if not isinstance(center, list) or len(center) != 2 or not isinstance(speed, (int, float)):
            raise ValueError("Original body and speed readback required")
        if abs(center[0] - branch.target_center_x_m) > 2.0 or speed > 0.2:
            raise ValueError("Target rest was not sustained")
        if (center[1] < 0) != (branch.side == "same"):
            raise ValueError("Rest occurred on wrong highway side")
    return {"observed_rest_frames": 40, "activity_target": branch.activity,
            "exception_target": branch.exception,
            "statutory_distance_verdict": "unresolved"}
