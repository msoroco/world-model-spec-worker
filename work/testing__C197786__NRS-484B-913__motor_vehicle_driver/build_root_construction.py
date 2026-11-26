"""Materialize the assignment-level handoff from the exact selected cases."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    first = json.loads((ROOT / manifest["cases"][0]["construction"]).read_text())
    files = {item["path"]: item["content"] for item in first["files"]}
    config = json.loads(files["config.json"])
    config["supported_case_ids"] = [item["case_id"] for item in manifest["cases"]]
    for camera in config["cameras"]:
        camera["pose_strategy"] = "reviewed original private-way source pose"
        camera["fov_deg"] = 90
    write(ROOT / "config.json", config)
    (ROOT / "runner.py").write_text(files["runner.py"])
    construction = dict(first)
    construction["diagnostic_only"] = False
    construction["measurement_plan"] = {
        "method": "source-joined 900-frame Native body and hose geometry",
        "source": "reviewed original private-way packet and sealed frames.jsonl",
    }
    construction["static_checks"] = ["reviewed six-source packet", "four-view 20 Hz source capture"]
    construction["termination_rules"] = ["900 synchronous ticks", "verified owner restoration"]
    construction["mechanisms"] = ["original hose actor", "source-joined ego passage"]
    construction["files"] = [
        {"path": "config.json", "content": (ROOT / "config.json").read_text()},
        {"path": "runner.py", "content": (ROOT / "runner.py").read_text()},
    ]
    write(ROOT / "construction.json", construction)
    plan["camera_plan"] = {
        "profile": "overview1080-capability",
        "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": camera["name"], "subject": "ego, hose and private-way passage",
                      "interval": "all 900 original ticks"} for camera in config["cameras"]],
    }
    plan["source_observation_mapping"] = {}
    if plan["observations"] and isinstance(plan["observations"][0], str):
        plan["observation_notes"] = plan["observations"]
    plan["observations"] = [{"name": item["name"], "mandatory": True}
                            for item in first["recording_description"]["channels"]]
    write(ROOT / "case-plan.json", plan)


if __name__ == "__main__":
    main()
