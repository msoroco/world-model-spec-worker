"""Exact NRS 484B.400(1) T-junction CPU delivery scope."""

AID = "testing__C399695__NRS-484B-400-1__motor_vehicle_driver"
LAW = "NRS-484B-400-1"
CELL = "C399695"
ACTOR = "motor_vehicle_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if i == 0 else 1280,
            "height": 1080 if i == 0 else 720, "fov_deg": 75,
            "pose_strategy": "reviewed T-junction approach, turn-lane boundary and connected exit"}
           for i, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ("intersection_and_highway", "source record", "sealed public-highway, non-alley T-junction and connected-exit survey"),
    ("conditional_lane_qualification", "source record", "independent reviewed NRS 484B.223(4) lane-design packet"),
    ("driver_and_intention", "source record", "original driver identity and independently declared right-turn route"),
    ("approach_lane_position", "lane/frame", "joined original Native body pose and lane/road ID during approach"),
    ("turn_lane_position", "lane/frame", "joined original Native body pose and junction/lane ID during right turn"),
    ("connected_departure", "road/frame", "joined original Native right-exit road and body pose"),
)
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second approach, turn and connected exit",
                  "reference_frame": "source-surveyed Native T junction, road and lane IDs",
                  "uncertainty": "Lane occupancy and a planned route do not establish legal compliance"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [{"name": "reviewed_t_junction_site", "unit": "source record",
                        "method": "sealed highway, lane qualification, geometry and connected-right-exit packet"}],
    "limitations": ["No numeric lane-entry deadline or legal lateral threshold is supplied.",
                    "Synthetic diagnostics prove software behavior only."],
}
