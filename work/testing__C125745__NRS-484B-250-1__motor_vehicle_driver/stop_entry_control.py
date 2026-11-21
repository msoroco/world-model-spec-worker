"""CPU-checkable approach controller for C125745(1) stop-sign constructions.

The controller stages a full stop and waits for measured conflict clearance.
It does not make a statutory yield, official-device, or physical success claim.
"""

import math


def _finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Finite " + label + " required")
    return float(value)


def step_ego(distance_to_stop_m, speed_mps, stopped_frames, conflict_clear,
             target_mps=5.0):
    """Return throttle, brake, new stop counter, and physical control phase.

    `conflict_clear` must come from full other-body geometry in original Native
    samples.  Two stationary 20 Hz frames near the sign are required before
    release.  That duration is an engineering interlock, not a legal threshold.
    """
    distance = _finite(distance_to_stop_m, "stop distance")
    speed = _finite(speed_mps, "speed")
    target = _finite(target_mps, "target speed")
    if speed < 0 or target <= 0 or type(stopped_frames) is not int or stopped_frames < 0:
        raise ValueError("Valid stop state and speed required")
    if type(conflict_clear) is not bool:
        raise ValueError("Measured conflict-clear boolean required")
    near = distance <= 1.5
    if stopped_frames < 2:
        stopped_frames = stopped_frames + 1 if near and speed <= 0.15 else 0
    if stopped_frames < 2:
        if distance > max(2.0, speed * speed / 3.0):
            return min(0.4, max(0.0, (target - speed) * 0.15)), 0.0, stopped_frames, "approach_stop"
        # Begin braking early enough for the planned low-speed diagnostic route.
        brake = max(0.25, min(1.0, (speed * speed / max(2 * max(distance, 0.2), 0.4)) / 4))
        return 0.0, brake, stopped_frames, "approach_stop"
    if not conflict_clear:
        return 0.0, 1.0, stopped_frames, "hold_for_other_body"
    return min(0.5, max(0.0, (target - speed) * 0.18)), 0.0, stopped_frames, "released"


def step_other(speed_mps, release_frame, frame, target_mps=5.0):
    """Release the other actor by a configured frame, regardless of outcome."""
    speed = _finite(speed_mps, "other speed")
    target = _finite(target_mps, "other target speed")
    if speed < 0 or target <= 0 or type(release_frame) is not int or type(frame) is not int or release_frame < 0 or frame < 0:
        raise ValueError("Valid other release state required")
    if frame < release_frame:
        return 0.0, 1.0, "held"
    return min(0.5, max(0.0, (target - speed) * 0.18)), min(0.5, max(0.0, (speed - target) * 0.2)), "released"
