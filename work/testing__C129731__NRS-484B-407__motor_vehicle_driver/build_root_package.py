"""Materialize the assignment entrypoint and camera plan from exact case work."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build() -> None:
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    case_ids = [case["case_id"] for case in plan["cases"]]
    selected = json.loads((HERE / "construction-distance_at_500ft.json").read_text())
    files = {item["path"]: item["content"] for item in selected["files"]}
    local = json.loads(files["config.json"])
    cameras = []
    for name, size, pose in (
            ("overview", (1920, 1080), "reviewed site overhead overview"),
            ("approach", (1280, 720), "reviewed approaching lanes"),
            ("reference_corner", (1280, 720), "reviewed curve and crest corner"),
            ("driver_reference", (1280, 720), "reviewed driver reference")):
        cameras.append({"name": name, "width": size[0], "height": size[1],
                        "pose_strategy": pose, "fov_deg": 90})
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "reversal and both approach lanes", "interval": "0-45 s"},
            {"view": "approach", "subject": "oncoming and following vehicles", "interval": "0-45 s"},
            {"view": "reference_corner", "subject": "curve, crest and governing road geometry", "interval": "0-45 s"},
            {"view": "driver_reference", "subject": "driver reference and sight rays", "interval": "0-45 s"},
        ],
        "physical_view_review": "pending original Native acquisition",
    }
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    config = {"assignment_id": HERE.name, "law_id": local["law_id"],
              "cell_id": local["cell_id"], "actor": local["actor"],
              "selected_case_id": local["selected_case_id"],
              "supported_case_ids": case_ids,
              "suffix": local["suffix"],
              "target_first_turn_distance_ft": local["target_first_turn_distance_ft"],
              "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
              "rate_hz": 20, "frame_count": 900, "duration_s": 45,
              "cameras": cameras, "required_atoms": [], "source_packets": [],
              "capture_selection": "source-gated exact manifest case",
              "actual_site_review": "pending original Native source review"}
    config_text = json.dumps(config, indent=2) + "\n"
    (HERE / "config.json").write_text(config_text)
    runner = files["runner.py"].replace(
        "config['cameras'] !=\n            ['overview', 'approach', 'reference_corner', 'driver_reference']",
        "[camera['name'] for camera in config['cameras']] !=\n            ['overview', 'approach', 'reference_corner', 'driver_reference']")
    (HERE / "runner.py").write_text(runner)
    world_restore = files["world_restore.py"]
    (HERE / "world_restore.py").write_text(world_restore)
    construction = {
        "law_id": local["law_id"], "cell_id": local["cell_id"],
        "actor": local["actor"], "case_id": local["selected_case_id"],
        "entrypoint": "runner.py",
        "recording_description": selected["recording_description"],
        "measurement_plan": {
            "requirements": [row["requirement"] for row in plan["requirement_dispositions"]],
            "procedure": "selected_analysis.py saved-only source-bound finalizer",
            "legal_visibility_judgment": "unresolved",
        },
        "static_checks": ["exact case and actor identity", "20 Hz 45-second frame map",
                           "four original RGB camera sources", "two-direction sight-ray source",
                           "saved Core/frame/video join"],
        "termination_rules": ["retain all 900 source frames and closure receipts",
                              "record physical failure flags without assigning a legal verdict"],
        "mechanisms": ["reviewed mountain-road curve or crest", "controlled reversal route",
                       "both incoming approach lanes", "source-gated four-view Native capture"],
        "files": [{"path": "config.json", "content": config_text},
                  {"path": "runner.py", "content": runner},
                  {"path": "world_restore.py", "content": world_restore}],
    }
    (HERE / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    print("Assignment root package materialized", len(case_ids), "cases")


if __name__ == "__main__":
    build()
