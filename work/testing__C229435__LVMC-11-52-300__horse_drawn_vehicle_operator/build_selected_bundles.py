"""Bind every exact case to a self-contained, source-hashed inline construction."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
WORK_REL = "work/" + ASSIGNMENT + "/"
SOURCE_NAMES = (
    "runner.py", "night_parking_construction.py", "night_parking_capture.py",
    "night_parking_native.py",
    "night_parking_measurement.py", "analysis.py", "comparison_audit.py",
    "tests/test_bundle.py",
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposals = json.loads((ROOT / "proposals/cases.json").read_text())
    by_id = {case["case_id"]: case for case in proposals["cases"]}
    ids = [case["case_id"] for case in plan["cases"]]
    for index, case in enumerate(plan["cases"]):
        ident = case["case_id"]
        suffix = ident.rsplit("__", 1)[-1]
        recording = by_id[ident]["recording_description"]
        config = {
            "assignment_id": ASSIGNMENT,
            "selected_case_id": ident,
            "supported_case_ids": ids,
            "law_id": plan["law_id"],
            "cell_id": plan["cell_id"],
            "actor": plan["actor"],
            "rate_hz": 20,
            "duration_s": plan["camera_plan"]["duration_s"],
            "parking_duration_s": case["design"]["duration_s"],
            "capture_queue_capacity": 4,
            "required_atoms": [],
            "source_packets": [],
            "cameras": [
                {"name": "overview", "width": 1920, "height": 1080,
                 "pose_strategy": "fixed surveyed street and both bodies", "fov_deg": 90},
                {"name": "approach", "width": 1280, "height": 720,
                 "pose_strategy": "fixed arrival departure and parked body", "fov_deg": 90},
                {"name": "reference_corner", "width": 1280, "height": 720,
                 "pose_strategy": "fixed surveyed street boundary and other vehicle", "fov_deg": 90},
                {"name": "driver_reference", "width": 1280, "height": 720,
                 "pose_strategy": "responsible person and carriage context", "fov_deg": 90},
            ],
            "physical_completion": {"criterion": "original_continuous_street_parking",
                                    "motion_source": "night-parking-trace.jsonl",
                                    "minimum_samples": 2,
                                    "engineering_tolerances_not_legal": True},
            "case": case,
        }
        files = [{"path": name, "source": WORK_REL + name,
                  "content": (ROOT / name).read_text()} for name in SOURCE_NAMES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2, ensure_ascii=False) + "\n"})
        bundle = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                  "actor": plan["actor"], "case_id": ident, "entrypoint": "runner.py",
                  "files": files,
                  "measurement_plan": [{"name": "nighttime_parking_episode",
                                        "method": "analysis.measure_night_parking",
                                        "sources": ["night-parking-sources.json", "context.json",
                                                    "classification.json", "activity.json",
                                                    "night-parking-trace.jsonl", "video_frames.jsonl"]}],
                  "recording_description": recording,
                  "static_checks": ["exact law and selected case binding",
                                    "source-hashed original map, municipal street, carriage build and person activity",
                                    "both original bodies and four-view frame identity"],
                  "termination_rules": ["36,101 continuous original 20 Hz ticks and retained source closure"],
                  "mechanisms": ["reviewed nonmotor carriage and other vehicle construction",
                                 "scheduled internal parking episode",
                                 "four synchronized original camera streams",
                                 "saved-only measurement and independent comparison audit"]}
        write_json(ROOT / "cases" / suffix / "construction.json", bundle)
        if index == 0:
            write_json(ROOT / "construction.json", bundle)
            write_json(ROOT / "config.json", config)


if __name__ == "__main__":
    build()
