"""Four original-camera acquisition views for the C111294 speed sweep."""
from __future__ import annotations

PROFILE = "c111294-speed-four-view-v1"


def camera_plan() -> list[dict]:
    return [
        {"name": "overview", "attachment": "ego", "xyz_m": [-12.0, 0.0, 6.0],
         "yaw_deg": 0.0, "pitch_deg": -18.0, "fov_deg": 100.0,
         "width": 1920, "height": 1080},
        {"name": "ego_forward", "attachment": "ego", "xyz_m": [1.6, 0.0, 1.8],
         "yaw_deg": 0.0, "pitch_deg": -3.0, "fov_deg": 90.0,
         "width": 1280, "height": 720},
        {"name": "ego_side", "attachment": "ego", "xyz_m": [0.0, 1.2, 2.1],
         "yaw_deg": 90.0, "pitch_deg": -8.0, "fov_deg": 100.0,
         "width": 1280, "height": 720},
        {"name": "junction", "attachment": "world", "xyz_m": [0.0, 0.0, 28.0],
         "yaw_deg": 0.0, "pitch_deg": -90.0, "fov_deg": 110.0,
         "width": 1280, "height": 720},
    ]


def check() -> dict:
    rows = camera_plan()
    if len(rows) != 4 or len({r["name"] for r in rows}) != 4:
        raise ValueError("Four distinct camera streams required")
    if (rows[0]["width"], rows[0]["height"]) != (1920, 1080):
        raise ValueError("Full-resolution overview required")
    if rows[-1]["attachment"] != "world" or rows[-1]["xyz_m"][2] < 20:
        raise ValueError("Fixed junction context camera missing")
    return {"profile": PROFILE, "views": rows, "rate_hz": 20,
            "frames_per_view": 480, "original_pixels_observed": False}
