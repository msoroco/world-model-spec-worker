"""Exact C380107 capture constants; engineering requests are not legal findings."""

ASSIGNMENT = "testing__C380107__NRS-484B-208-1__motor_vehicle_driver"
LAW = "NRS-484B-208-1"
CELL = "C380107"
ACTOR = "motor_vehicle_driver"
CAMERAS = [
    {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 75,
     "pose_strategy": "reviewed original site camera pose"},
    {"name": "approach", "width": 1280, "height": 720, "fov_deg": 75,
     "pose_strategy": "reviewed original site camera pose"},
    {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 75,
     "pose_strategy": "reviewed original site camera pose"},
    {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 75,
     "pose_strategy": "reviewed original site camera pose"},
]
