"""Exact right-turn-only lane purpose delivery contract."""

AID = "testing__C399695__NRS-484B-223-4a__motor_vehicle_driver"
LAW = "NRS-484B-223-4a"
CELL = "C399695"
ACTOR = "motor_vehicle_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if i == 0 else 1280,
            "height": 1080 if i == 0 else 720, "fov_deg": 75,
            "pose_strategy": "surveyed T intersection, exclusive right-turn lane and vehicle route"}
           for i, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ("public_highway_and_lane_design", "source record", "sealed public-highway and single exclusive right-turn-lane survey"),
    ("vehicle_and_driver_identity", "source record", "original Native vehicle and driver identity"),
    ("right_turn_lane_occupancy", "lane/frame", "original Native lane and road ID readback at 20 Hz"),
    ("declared_maneuver_purpose", "source record", "independent purpose declaration before lane entry"),
    ("connected_right_turn_route", "source record", "surveyed T-junction right exit connectivity"),
    ("observed_departure_route", "road/frame", "original Native road ID, pose and maneuver history"),
    ("vehicle_motion", "world meters/frame", "original speed, position and controller history"),
)
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second right-turn-lane approach and departure",
                  "reference_frame": "source-surveyed Native T junction and lane IDs",
                  "uncertainty": "Lane use or eventual turn does not prove purpose at lane entry"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [{"name": "reviewed_t_junction_site", "unit": "source record",
                        "method": "sealed public highway, lane design, route connectivity and purpose packet"}],
    "limitations": ["No numeric lane-occupancy deadline appears in the exact law.",
                    "A completed right turn alone does not prove prior purpose.",
                    "Synthetic diagnostics prove software behavior only."]}
