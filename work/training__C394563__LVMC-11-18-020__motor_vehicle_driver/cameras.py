"""Four synchronized source views for the signed school crossing."""


def camera_plan() -> list[dict]:
    return [
        {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 90,
         "attachment": "world", "xyz_m": [8, -22, 32],
         "purpose": "vehicle, pedestrian, crossing and school sign context"},
        {"name": "approach", "width": 1280, "height": 720, "fov_deg": 80,
         "attachment": "world", "xyz_m": [-14, -12, 12],
         "purpose": "vehicle front entry and yellow crossing"},
        {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 90,
         "attachment": "world", "xyz_m": [-5, 7, 9],
         "purpose": "person and approach-side crossing occupation"},
        {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 90,
         "attachment": "ego", "xyz_m": [1.1, 0, 1.7],
         "purpose": "advance School-Xing sign and crossing approach"},
    ]
