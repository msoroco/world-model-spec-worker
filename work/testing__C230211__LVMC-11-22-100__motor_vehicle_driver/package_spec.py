"""Exact protected-pavement delivery identity and original capture profile."""

AID = "testing__C230211__LVMC-11-22-100__motor_vehicle_driver"
LAW = "LVMC-11-22-100"
CELL = "C230211"
ACTOR = "motor_vehicle_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [
    {"name": name, "width": 1920 if index == 0 else 1280,
     "height": 1080 if index == 0 else 720, "fov_deg": 75,
     "pose_strategy": "surveyed protected pavement, warning, ego route and work activity"}
    for index, name in enumerate(CAMERA_NAMES)
]
CHANNELS = (
    ("vehicle_motion", "world meters/frame", "original ego body, position and speed"),
    ("pavement_condition", "source record", "sealed newly laid or repaired condition"),
    ("pavement_extent", "world meters", "surveyed pavement bounds and body crossing"),
    ("protection_geometry", "world meters", "spawned barrier/person/sign readback"),
    ("protection_placement_time", "original time", "warning placement before approach"),
    ("employment", "source record", "driver employment and same-pavement identity"),
    ("work_activity", "original time", "active paving or repair during passage"),
    ("camera_frame_identity", "original frame", "four synchronized camera streams"),
)
RECORDING = {
    "channels": [
        {"name": name, "unit": unit, "method": method,
         "sampling_rate_hz": 20, "time_window": "45-second pavement approach and passage",
         "reference_frame": "reviewed Native pavement rectangle and warning geometry",
         "uncertainty": "Physical observations do not decide statutory application"}
        for name, unit, method in CHANNELS
    ],
    "context_inputs": [
        {"name": "reviewed_native_pavement_site", "unit": "source record",
         "method": "sealed map, pavement, warning, route and employment packet"}
    ],
    "limitations": [
        "Synthetic fixtures prove software compatibility only.",
        "Newness, warning effect and employee exception require original review."
    ]
}
