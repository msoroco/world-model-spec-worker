"""Deterministically author the five exact inline Native parking constructions."""

import json
from pathlib import Path

from comparison_audit import CASES
from parking_place import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
CAMERAS = [
    {"name": name, "width": width, "height": height, "pose_strategy": strategy,
     "fov_deg": 90}
    for name, width, height, strategy in (
        ("overview", 1920, 1080, "fixed overview of site, device and vehicle"),
        ("approach", 1280, 720, "fixed vehicle approach and device"),
        ("reference_corner", 1280, 720, "fixed designated boundary and curb"),
        ("driver_reference", 1280, 720, "vehicle mounted forward view"))]
CHANNEL_NAMES = ("vehicle_body_history", "vehicle_speed_and_control_history",
                 "designated_place_geometry", "device_identity_history",
                 "place_context_history", "curb_person_history",
                 "conduct_phase_history", "camera_frame_map")
RECORDING = {
    "channels": [{"name": name, "unit": "structured record", "sampling_rate_hz": 20,
                  "method": "Original CARLA frame acquisition and saved-only extraction",
                  "time_window": "approach through stationary observation",
                  "reference_frame": "CARLA world with original frame and time",
                  "uncertainty": "20 Hz sampling and simulator body precision"}
                 for name in CHANNEL_NAMES],
    "context_inputs": [{"name": name, "unit": "structured record",
                        "method": "Reviewed original source binding and Native actor/map readback"}
                       for name in ("official_device_context", "designated_extent_context",
                                    "hazard_or_congestion_context")],
    "limitations": ["Legal official status, hazardous or congested character, and stop/stand/park conduct require independent review.",
                    "Actual device legibility and vehicle footprint require local camera review."]}
SOURCE_FILES = ("runner.py", "native_parking.py", "parking_place.py", "site_review.py",
                "comparison_audit.py", "analysis.py", "tests/test_bundle.py")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def author():
    for i, (suffix, (conduct, footprint, context)) in enumerate(CASES.items()):
        case_id = ASSIGNMENT + "__" + suffix
        config = {"assignment_id": ASSIGNMENT, "selected_case_id": case_id,
                  "supported_case_ids": [ASSIGNMENT + "__" + name for name in CASES],
                  "law_id": "NRS-484B-500", "cell_id": "C229439", "actor": "vehicle_parker",
                  "rate_hz": 20, "duration_s": 20, "required_atoms": [], "source_packets": [],
                  "cameras": CAMERAS,
                  "physical_completion": {"criterion": "travel_progress", "motion_source": "parking-history.jsonl",
                                          "position_key": "position_m", "minimum_progress_m": 5,
                                          "minimum_samples": 2, "engineering_tolerances_not_legal": True},
                  "case": {"case_id": case_id, "requested_conduct": conduct,
                           "requested_footprint": footprint,
                           "place_context_for_review": context,
                           "recording_description": RECORDING}}
        files = [{"path": name, "source": str((ROOT / name).relative_to(ROOT.parents[1])),
                  "content": (ROOT / name).read_text(encoding="utf-8")}
                 for name in SOURCE_FILES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        construction = {"law_id": "NRS-484B-500", "cell_id": "C229439",
                        "actor": "vehicle_parker", "case_id": case_id,
                        "entrypoint": "runner.py", "files": files,
                        "measurement_plan": [{"name": "designated_parking_measurement",
                                              "method": "analysis.measure_saved",
                                              "sources": ["parking-history.jsonl", "parking-context.json",
                                                          "video_frames.jsonl", "trace.jsonl"]}],
                        "recording_description": RECORDING,
                        "static_checks": ["exact case and site source identities", "vehicle footprint and device prop readback"],
                        "termination_rules": ["20 seconds of original 20 Hz approach and halt observation"],
                        "mechanisms": ["reviewed device prop spawn", "distance controller", "body footprint readback",
                                       "synchronized four-camera capture", "saved-only finalizer"]}
        if i == 0:
            write(ROOT / "config.json", config)
            write(ROOT / "construction.json", construction)
        else:
            write(ROOT / "cases" / suffix / "config.json", config)
            write(ROOT / "cases" / suffix / "construction.json", construction)


if __name__ == "__main__":
    author()
