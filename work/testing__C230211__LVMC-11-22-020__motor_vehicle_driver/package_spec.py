"""Exact barrier delivery identity and original recording contract."""

AID = "testing__C230211__LVMC-11-22-020__motor_vehicle_driver"
LAW = "LVMC-11-22-020"
CELL = "C230211"
ACTOR = "motor_vehicle_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if index == 0 else 1280,
            "height": 1080 if index == 0 else 720, "fov_deg": 75,
            "pose_strategy": "surveyed city highway, barrier and moving ego body"}
           for index, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ("ego_body_motion", "world meters/frame", "original 20 Hz vehicle footprint, position and speed"),
    ("barrier_body_clearance", "meters/frame", "original body-to-source-barrier distance and contact readback"),
    ("highway_city_context", "source record", "sealed Native road, City status and surrounding conditions"),
    ("route_realization", "world meters/frame", "original approach and passage of selected connected route"),
    ("camera_frame_identity", "original frame", "four original synchronized camera streams"),
)
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second barrier approach and passage",
                  "reference_frame": "reviewed Native map, road bounds and barrier rectangle",
                  "uncertainty": "Physical measurements do not decide careless or imprudent driving"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [{"name": "reviewed_native_barrier_site", "unit": "source record",
                        "method": "sealed map, highway, barrier and surrounding-conditions packet"}],
    "limitations": ["Synthetic fixtures prove software compatibility only.",
                    "Careless or imprudent remains for independent human legal review."]}
