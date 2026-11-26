"""Exact package identity and shared 20 Hz capture description."""

from school_lane_controls import ASSIGNMENT, VARIANTS

LAW = "LVMC-11-46-030"
CELL = "C422976"
ACTOR = "motor_vehicle_driver"
CASES = [ASSIGNMENT + "__" + variant.suffix for variant in VARIANTS]
CAMERAS = [
    {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 75,
     "pose_strategy": "whole school pedestrian lane, warnings and vehicle"},
    {"name": "approach", "width": 1280, "height": 720, "fov_deg": 75,
     "pose_strategy": "vehicle connected approach and stopping station"},
    {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 75,
     "pose_strategy": "nearest lane side and vehicle body reference"},
    {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 75,
     "pose_strategy": "human or device warning and release gesture"},
]


def recording_description():
    channels = []
    for name, unit, method in (
        ("school_lane_nearest_side_geometry", "m", "SHA-sealed reviewed lane side and station in original world frame"),
        ("ego_reference_station_and_speed", "m and m/s", "original Native body reference station and velocity at every world tick"),
        ("human_warning_children_and_release", "source observation", "original human identity, child presence, warning, gesture and departure readback"),
        ("device_warning_and_release", "source observation", "original device identity, warning and raised/stopped/removed state"),
        ("four_synchronized_camera_views", "original frames", "four Native RGB frames joined to each original world tick"),
        ("original_warning_onset_s", "s", "first original 20 Hz frame with source-bound child-crossing warning"),
        ("original_departure_onset_s", "s", "first original 20 Hz frame with source-bound person departure"),
    ):
        channels.append({"name": name, "unit": unit, "method": method,
                         "reference_frame": "reviewed original school-lane approach and Native world frame",
                         "sampling_rate_hz": 20, "time_window": "all 900 original ticks",
                         "uncertainty": "physical visibility, reference convention and legal interpretation pending"})
    return {"channels": channels, "context_inputs": [{
                "name": "municipal jurisdiction and reviewed school-lane authority",
                "unit": "source record", "method": "SHA-256-sealed original site, map, geometry and actor packet"}],
            "limitations": ["Engineering station targets do not establish statutory fifty-foot compliance.",
                            "Original human go gesture, departure locality and device release require independent review."]}
