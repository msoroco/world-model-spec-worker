"""Deterministic Native request for the C109166 diagonal crossing pair.

Coordinates are authored diagnostic geometry. A local map/device survey must
replace them before a physical case can be selected or executed.
"""
from __future__ import annotations

import math

RATE_HZ = 20
FRAMES = 600
START_FRAME = 100
END_FRAME = 340
START_XY = (-6.0, -6.0)
END_XY = (6.0, 6.0)
CAMERAS = (
    ("overview", 1920, 1080, (0.0, 0.0, 24.0), (-90.0, 0.0, 0.0)),
    ("approach", 1280, 720, (-12.0, -12.0, 5.0), (-18.0, 45.0, 0.0)),
    ("reference_corner", 1280, 720, (8.0, -8.0, 5.0), (-17.0, 135.0, 0.0)),
    ("driver_reference", 1280, 720, (-10.0, -10.0, 1.6), (0.0, 45.0, 0.0)),
)


def position(frame: int) -> tuple[float, float]:
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("frame outside 600-frame acquisition")
    phase = max(0.0, min(1.0, (frame - START_FRAME) / (END_FRAME - START_FRAME)))
    return (START_XY[0] + phase * (END_XY[0] - START_XY[0]),
            START_XY[1] + phase * (END_XY[1] - START_XY[1]))


def command(frame: int) -> dict:
    """Return the frame's walker request; readback still governs measurement."""
    xy = position(frame)
    moving = START_FRAME <= frame < END_FRAME
    direction = tuple((b - a) / math.dist(START_XY, END_XY)
                      for a, b in zip(START_XY, END_XY))
    speed = math.dist(START_XY, END_XY) * RATE_HZ / (END_FRAME - START_FRAME)
    return {"frame": frame, "time_s": frame / RATE_HZ, "target_xy_m": xy,
            "walker_direction_xyz": (*direction, 0.0),
            "walker_speed_mps": speed if moving else 0.0,
            "source_kind": "authored_native_request", "measured_position": None}


def apply_walker_control(walker, carla, frame: int) -> dict:
    """Issue CARLA WalkerControl; Native position is sampled separately."""
    row = command(frame)
    direction = carla.Vector3D(*row["walker_direction_xyz"])
    walker.apply_control(carla.WalkerControl(direction, row["walker_speed_mps"], False))
    return row


def camera_plan() -> list[dict]:
    return [{"name": name, "width": width, "height": height,
             "fps": RATE_HZ, "location_xyz_m": location,
             "rotation_pitch_yaw_roll_deg": rotation,
             "source_required": True}
            for name, width, height, location, rotation in CAMERAS]


def validate_pair(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """Prove that display request alone differs across the paired controllers."""
    if len(rows_a) != FRAMES or len(rows_b) != FRAMES:
        raise ValueError("full 600-frame pair required")
    for frame, (a, b) in enumerate(zip(rows_a, rows_b)):
        expected = command(frame)
        for row in (a, b):
            if any(row.get(key) != value for key, value in expected.items()):
                raise ValueError("paired walker motion changed")
        if a.get("device_display_request") != "diagonal_walk_requested":
            raise ValueError("authorized display request missing")
        if b.get("device_display_request") != "no_diagonal_permission":
            raise ValueError("unauthorized display request missing")
        if a.get("official_device_verified") is not False or b.get("official_device_verified") is not False:
            raise ValueError("official authority overstated")
    return {"frames": FRAMES, "rate_hz": RATE_HZ, "duration_s": FRAMES / RATE_HZ,
            "path_length_m": round(math.dist(START_XY, END_XY), 6),
            "paired_motion_identical": True, "camera_names": [x["name"] for x in camera_plan()],
            "official_device_verified": False, "physical_completion_claimed": False}
