"""Exact NRS 484B.210(2) original right-pass delivery contract."""

AID = "testing__C178759__NRS-484B-210-2__motor_vehicle_driver"
LAW = "NRS-484B-210-2"
CELL = "C178759"
ACTOR = "motor_vehicle_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if i == 0 else 1280,
            "height": 1080 if i == 0 else 720, "fov_deg": 75,
            "pose_strategy": "surveyed paved right lane and both moving vehicle bodies"}
           for i, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ("qualifying_vehicles_and_driver", "source record", "original Native ego, target and driver identities"),
    ("right_lane_and_pavement", "source record", "surveyed right lane and paved boundary"),
    ("whole_right_pass", "world meters/frame", "original behind, alongside-right and ahead body envelopes"),
    ("approach_space", "meters/frame", "original body gap and closing time"),
    ("lateral_space", "meters/frame", "original side-by-side body clearance"),
    ("conflict_space", "meters/frame", "original crossing actor body separation when present"),
    ("motion_context", "world meters/frame", "original speed, brake and steer history"),
)
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second right-pass approach and completion",
                  "reference_frame": "source-surveyed Native paved road and actor body frames",
                  "uncertainty": "Motion measurements do not decide conditions permitting safety"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [{"name": "reviewed_native_right_pass_site", "unit": "source record",
                        "method": "source-sealed map, pavement, actors and surrounding traffic"}],
    "limitations": ["Synthetic diagnostics prove software compatibility only.",
                    "Safety condition requires independent human legal review."]}
