"""Materialize the exact-case dispatch contract and four-view root configuration."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    ids = [case["case_id"] for case in plan["cases"]]
    if len(ids) != 4 or len(set(ids)) != 4:
        raise ValueError("Root package requires four exact cases")
    config = {
        "assignment_id": HERE.name, "law_id": plan["law_id"], "cell_id": plan["cell_id"],
        "actor": plan["actor"], "supported_case_ids": ids,
        "rate_hz": 20, "duration_s": 45, "frame_count": 900,
        "required_atoms": [], "source_packets": [],
        "cameras": [{"name": name, "width": width, "height": height, "fov_deg": 75,
                     "pose_strategy": "reviewed original left-turn and receiving-traffic coverage"}
                    for name, width, height in (
                        ("overview", 1920, 1080), ("approach", 1280, 720),
                        ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))],
    }
    (HERE / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    construction = {
        "law_id": plan["law_id"], "cell_id": plan["cell_id"], "actor": plan["actor"],
        "entrypoint": "runner.py", "recording_description": plan["cases"][0]["recording_description"],
        "measurement_plan": {"purpose": "Observe original 900-frame 20 Hz post-turn center-lane travel, turn and merge, and censored no-merge cases",
                             "case_ids": ids},
        "static_checks": ["pinned runtime atom preflight", "four exact construction SHA checks",
                          "source-bound Native runner preflight", "selected CPU compatibility"],
        "termination_rules": ["45 seconds or 900 original frames", "fail closed on missing site, camera or frame evidence"],
        "mechanisms": ["source-gated left turn into exclusive shared center lane",
                       "same-tick PipelineCapture and four RGB cameras",
                       "saved-only measurement, Core/Lean decode and independent comparison"],
        "files": [{"path": name, "content": (HERE / name).read_text()}
                  for name in ("runner.py", "config.json")],
    }
    (HERE / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    print("root dispatch package includes", len(ids), "exact cases")


if __name__ == "__main__":
    build()
