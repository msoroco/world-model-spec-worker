"""Build four-view capture metadata for exact railway instruction cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import railway_7b as law

HERE = Path(__file__).resolve().parent
AID = HERE.name
CHANNELS = (
    "rail_crossing_geometry", "device_identity_and_officiality", "device_indication_history",
    "governed_movement", "officer_identity_and_direction_history", "driver_identity",
    "original_body_entry_exit", "actual_speed_and_brake", "four_camera_frame_join",
)


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def build():
    plan = HERE / "case-plan.json"
    case_id = AID + "__device_stop_halt"
    description = {
        "channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                      "time_window": "all 900 original Native frames",
                      "reference_frame": "reviewed railway crossing and original CARLA world",
                      "method": "Retain source-hashed original site and frame-joined " + name,
                      "uncertainty": "officiality, instruction authenticity and legal judgment require independent review"}
                     for name in CHANNELS],
        "context_inputs": [{"name": "reviewed_railway_site", "unit": "source",
                            "method": "independent source-hashed crossing, device and officer site packet"}],
        "limitations": ["CPU fixtures establish software shape only; original indication, driver response, officiality and legal judgment require review."],
    }
    cameras = [
        {"name": name, "width": width, "height": height, "fov_deg": 80,
         "pose_strategy": "reviewed crossing entry and exit, governed movement, device or officer, complete vehicle"}
        for name, width, height in (
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))]
    config = {"assignment_id": AID, "law_id": law.LAW, "cell_id": law.CELL,
              "actor": law.ACTOR, "catalog_control": "traffic_control_device",
              "selected_case_id": case_id, "supported_case_ids": [AID + "__" + name for name in law.CASES],
              "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
              "duration_s": 45, "rate_hz": 20, "required_atoms": [], "source_packets": [],
              "approach_start_m": 55.0, "cameras": cameras,
              "case": {"case_id": case_id, "recording_description": description}}
    write(HERE / "config.json", config)
    return config


if __name__ == "__main__":
    build()
