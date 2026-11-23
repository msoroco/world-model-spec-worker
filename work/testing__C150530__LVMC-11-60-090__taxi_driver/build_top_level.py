"""Materialize the reusable top-level CPU package without readiness claims."""
from __future__ import annotations

import json
from pathlib import Path

from build_construction_draft import ROOT, ASSIGNMENT, build as draft_build
from recording_description import build as recording_description


def build() -> dict:
    near = draft_build("near_stand")
    config = {
        "assignment_id": ASSIGNMENT,
        "selected_case_id": ASSIGNMENT + "__near_stand",
        "supported_case_ids": [ASSIGNMENT + "__" + case for case in
                               ("near_stand", "far_stand", "near_stand_straight")],
        "law_id": "LVMC-11-60-090", "cell_id": "C150530", "actor": "taxi_driver",
        "rate_hz": 20, "duration_s": 35.0,
        "required_atoms": [], "source_packets": [],
        "cameras": [
            {"name": name, "width": width, "height": height,
             "pose_strategy": strategy, "fov_deg": 90}
            for name, width, height, strategy in (
                ("overview", 1920, 1080, "fixed stand-to-junction overhead"),
                ("approach", 1280, 720, "fixed stand and posted-notice view"),
                ("reference_corner", 1280, 720, "fixed first-junction view"),
                ("driver_reference", 1280, 720, "ego mounted forward view"),
            )],
        "case": {"case_id": ASSIGNMENT + "__near_stand",
                 "recording_description": recording_description()},
        "physical_completion": {"criterion": "first_junction_exit",
                                "motion_source": "original-trace.jsonl",
                                "minimum_samples": 4,
                                "engineering_tolerances_not_legal": True},
        "documentary_status": "genuine original context packets still required",
    }
    files = []
    for item in near["files"]:
        if item["path"] == "config.json":
            files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        else:
            files.append(item)
    return {
        "law_id": "LVMC-11-60-090", "cell_id": "C150530", "actor": "taxi_driver",
        "case_id": ASSIGNMENT + "__near_stand", "entrypoint": "runner.py",
        "files": files, "recording_description": recording_description(),
        "mechanisms": ["source-reviewed cab and stand context join",
                       "one-way authored stand departure and first-junction route",
                       "four original synchronized camera streams and composed review video",
                       "source-hashed saved turn measurement"],
        "measurement_plan": {"turn": "Original 20 Hz cab road/lane, position and heading through first street intersection; documentary applicability pending"},
        "static_checks": ["exact OpenDRIVE topology and posted-notice geometry",
                          "source packet hashes and quotes required before Native capture"],
        "termination_rules": ["stop after fixed 35 s original capture or explicit physical failure"],
        "status": "partial CPU package; source packets and strict delivery receipts pending",
    }


def main() -> None:
    construction = build()
    files = {item["path"]: item["content"] for item in construction["files"]}
    (ROOT / "runner.py").write_text(files["runner.py"])
    (ROOT / "config.json").write_text(files["config.json"])
    (ROOT / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")


if __name__ == "__main__":
    main()
