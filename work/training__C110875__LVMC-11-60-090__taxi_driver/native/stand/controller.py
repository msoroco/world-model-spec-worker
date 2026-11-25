"""Geometry-target taxi controller. It requests motion; it proves none."""
import math

FRAMES = 600
RATE_HZ = 20
FIRST_X = 80.0


def target(direction, x, y):
    if direction not in ("right", "straight"):
        raise ValueError("Unknown first-intersection route")
    if direction == "right" and x >= 76:
        return (80.0, max(-75.0, y - 5.0), -90.0)
    return (min(145.0, x + 8.0), -1.75, 0.0)


def command(direction, x, y, heading_deg, speed_mps, *, gain=0.018):
    if not all(math.isfinite(v) for v in (x, y, heading_deg, speed_mps, gain)):
        raise ValueError("Nonfinite observed control input")
    if speed_mps < 0 or gain <= 0:
        raise ValueError("Invalid speed or steering gain")
    tx, ty, wanted_heading = target(direction, x, y)
    # Native CARLA y is mirrored relative to authored OpenDRIVE; the sign of
    # the heading error is checked again against original trajectory samples.
    desired = math.degrees(math.atan2(ty - y, tx - x))
    error = (desired - heading_deg + 180) % 360 - 180
    steer = max(-0.65, min(0.65, gain * error))
    throttle = max(0.0, min(0.55, 0.25 + 0.08 * (5.0 - speed_mps)))
    brake = 0.0 if speed_mps <= 7.0 else min(0.4, 0.08 * (speed_mps - 7.0))
    return {"throttle": throttle, "brake": brake, "steer": steer,
            "target_xy_m": [tx, ty], "target_heading_deg": wanted_heading,
            "observed_speed_mps": speed_mps}
