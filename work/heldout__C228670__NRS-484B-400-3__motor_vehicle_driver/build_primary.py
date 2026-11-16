"""Materialize the first exact source-surveyed turn construction."""

import json
from pathlib import Path

from turn_native_capture import CAMERAS
from turn_native_plan import ASSIGNMENT, OFFSETS_M


ROOT = Path(__file__).resolve().parent
CASE = ASSIGNMENT + "__centerline_approach_left_curb_departure"
CHANNELS = (
    ("approach_body_to_centerline", "m", "original four-corner signed offsets from surveyed approach centerline"),
    ("entry_body_right_of_centerline", "boolean and m", "original entry footprint right of surveyed centerline"),
    ("departure_body_to_left_curb", "m", "original four-corner distances from surveyed destination left curb"),
    ("highway_directions", "lane directions", "source-hashed Native waypoint direction inventory"),
)
FILES = ("runner.py", "turn_native_plan.py",
         "turn_native_capture.py", "turn_source_recorder.py", "route_survey.py",
         "body_position.py", "turn_position_finalizer.py",
         "tests/test_body_position.py", "tests/test_route_survey.py")


def build():
    description = {
        "channels": [{"name": name, "unit": unit, "sampling_rate_hz": 20,
                      "method": method, "time_window": "all relevant original turn frames",
                      "reference_frame": "source-surveyed Native road geometry",
                      "uncertainty": "public access, legal proximity and camera visibility require original review"}
                     for name, unit, method in CHANNELS],
        "context_inputs": ["source-hashed Native XODR route survey", "original four-camera RGB"],
        "limitations": ["No legal distance threshold or physical acceptance inferred from CPU fixtures"]}
    cameras = [{"name": name, "width": spec[2][0], "height": spec[2][1],
                "pose_strategy": "subject-mounted provisional turn view", "fov_deg": spec[3]}
               for name, spec in CAMERAS.items()]
    config = {"selected_case_id": CASE, "law_id": "NRS-484B-400-3", "cell_id": "C228670",
              "actor": "motor_vehicle_driver", "rate_hz": 20, "frames": 160, "duration_s": 8,
              "required_atoms": [], "source_packets": [], "cameras": cameras,
              "supported_case_ids": [ASSIGNMENT + "__" + suffix for suffix in OFFSETS_M],
              "case": {"case_id": CASE, "recording_description": description},
              "engineering": {"approach_target_offset_m": 1.2,
                              "departure_target_offset_m": 1.2,
                              "route_source": "Native XODR survey supplied with exact SHA-256 at capture"}}
    (ROOT / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    files = [{"path": "config.json", "content": (ROOT / "config.json").read_text()}]
    for name in FILES:
        path = ROOT / name
        if not path.is_file():
            raise ValueError("Construction source missing: " + name)
        files.append({"path": name, "content": path.read_text()})
    construction = {"format": "worker-construction-proposal", "case_id": CASE,
                    "law_id": "NRS-484B-400-3", "cell_id": "C228670",
                    "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                    "recording_description": description, "files": files,
                    "measurement_plan": {"original_rows": ["route_survey_original.json",
                                                           "body_corners_original.jsonl",
                                                           "video_frames.jsonl", "trace.jsonl"],
                                         "source_video": "overview.mkv",
                                         "saved_finalizer": "turn_position_finalizer.py",
                                         "review_required": "source-backed road status, physical pixels and legal proximity"},
                    "static_checks": ["runner.py --check"],
                    "termination_rules": ["160 original 20 Hz frames or explicit failure"],
                    "mechanisms": ["source-hashed Native two-directional approach and one-way exit survey",
                                   "separate approach and departure body target offsets",
                                   "four synchronized original RGB cameras",
                                   "original full-body corners and saved-only source-joined measurements"]}
    (ROOT / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    return CASE


if __name__ == "__main__":
    print(build())
