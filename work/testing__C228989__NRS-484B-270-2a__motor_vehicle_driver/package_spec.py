"""Exact NRS 484B.270(2)(a) package identities and recording channels."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = "testing__C228989__NRS-484B-270-2a__motor_vehicle_driver"
LAW = "NRS-484B-270-2a"
CELL = "C228989"
ACTOR = "motor_vehicle_driver"
CAMERA_NAMES = ("overview", "approach", "reference_corner", "driver_reference")
CAMERAS = [{"name": name, "width": 1920 if index == 0 else 1280,
            "height": 1080 if index == 0 else 720, "fov_deg": 75,
            "pose_strategy": "reviewed road, initial rider and immediate-left lane"}
           for index, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ("ego_control_body", "world-space vertices", "original 20 Hz motor-vehicle and qualifying control eight-vertex bodies"),
    ("lane_topology", "source record", "source-hashed lane IDs, direction, adjacency and restrictions"),
    ("left_lane_traffic", "actor inventory", "original 20 Hz left-lane occupants, obstructions and surrounding trajectories"),
    ("ego_lane_and_pass", "lane ID and frame", "original ego lane and first full-body pass frame"),
    ("relative_motion", "m/s", "original speed and longitudinal separation histories"),
    ("camera_frame_identity", "frame ID", "four synchronized original camera streams"),
)
RECORDING = {
    "channels": [{"name": name, "unit": unit, "method": method,
                  "sampling_rate_hz": 20, "time_window": "45-second overtaking interval",
                  "reference_frame": "source-sealed original Native frame and world-space road axis",
                  "uncertainty": "original physical realization and legal judgment require local review"}
                 for name, unit, method in CHANNELS],
    "context_inputs": [{"name": "reviewed_native_lane_packet", "unit": "source record",
                        "method": "source-hashed map, lane, actor, restriction and traffic inventory"}],
    "limitations": ["Synthetic fixtures establish software compatibility only.",
                    "Due care, lane availability and reasonable safety have no invented legal cutoffs."]}
