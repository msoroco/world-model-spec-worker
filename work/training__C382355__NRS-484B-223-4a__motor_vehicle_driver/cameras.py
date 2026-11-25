"""Four synchronized camera policies; image coverage remains unverified."""

PROFILE = "overview1080-capability-v1"
RATE_HZ = 20


def camera_plan(candidate="primary"):
    if candidate not in ("primary", "fallback1", "fallback2", "fallback3"):
        raise ValueError("Unknown construction candidate")
    approach_z = 4.5 if candidate == "fallback3" else 3.2
    approach_fov = 105 if candidate == "fallback3" else 90
    return [
        {"name":"overview", "width":1920, "height":1080, "fov_deg":75,
         "attachment":"world", "xyz_m":[-18,25,42], "pitch_deg":-62,
         "purpose":"junction, right-turn lane, intersection and entire turn"},
        {"name":"approach", "width":1280, "height":720, "fov_deg":approach_fov,
         "attachment":"ego", "xyz_m":[-8,0,approach_z], "pitch_deg":-17,
         "purpose":"complete ego body, right-turn lane and lane marking"},
        {"name":"reference_corner", "width":1280, "height":720, "fov_deg":90,
         "attachment":"world", "xyz_m":[-8,8,9], "pitch_deg":-30,
         "purpose":"right-turn-lane entry and physical right-only marking"},
        {"name":"driver_reference", "width":1280, "height":720, "fov_deg":105,
         "attachment":"ego", "xyz_m":[1.0,0,1.5], "pitch_deg":-2,
         "purpose":"subject forward reference; does not prove perception"},
    ]
