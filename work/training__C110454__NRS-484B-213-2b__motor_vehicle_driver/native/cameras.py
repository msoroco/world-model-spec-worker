"""Four synchronized C110454 camera proposals; pixels require a GPU run."""

def camera_plan(candidate="primary"):
    if candidate not in ("primary", "fallback1", "fallback2", "fallback3"):
        raise ValueError("Unknown candidate")
    fov = 105 if candidate == "fallback3" else 90
    return [
        {"name":"overview", "width":1920, "height":1080, "fov_deg":fov,
         "attachment":"world", "xyz_m":[-12,-20,48], "pitch_deg":-60},
        {"name":"approach", "width":1280, "height":720, "fov_deg":90,
         "attachment":"world", "xyz_m":[-33,-14,18], "pitch_deg":-40},
        {"name":"intersection", "width":1280, "height":720, "fov_deg":90,
         "attachment":"world", "xyz_m":[0,-12,15], "pitch_deg":-50},
        {"name":"parking", "width":1280, "height":720, "fov_deg":90,
         "attachment":"world", "xyz_m":[20,-15,14], "pitch_deg":-55},
    ]
