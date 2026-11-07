"""Four synchronized view specifications for the hill and turn."""

def camera_plan(candidate):
    if candidate not in ("primary", "fallback1", "fallback2", "fallback3"):
        raise ValueError("Unknown candidate")
    return [
        {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 80,
         "attachment": "world", "xyz_m": [-30, -30, 35], "pitch_deg": -35},
        {"name": "approach", "width": 1280, "height": 720,
         "fov_deg": 105 if candidate == "fallback3" else 90,
         "attachment": "ego", "xyz_m": [-8, 0, 4.5 if candidate == "fallback3" else 3.5],
         "pitch_deg": -15},
        {"name": "signal_close", "width": 1280, "height": 720, "fov_deg": 75,
         "attachment": "ego", "xyz_m": [-6, -3, 2.5], "pitch_deg": -10},
        {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 100,
         "attachment": "ego", "xyz_m": [1, 0, 1.5], "pitch_deg": -2},
    ]
