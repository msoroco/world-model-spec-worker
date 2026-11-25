"""Assemble the assignment-level dispatch contract from its exact case inputs."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    cases = [entry["case_id"] for entry in manifest["cases"]]
    primary = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    selected_config = json.loads(next(f["content"] for f in primary["files"] if f["path"] == "config.json"))
    config = dict(selected_config)
    config.update(assignment_id=AID, selected_case_id=cases[0], supported_case_ids=cases,
                  cameras=[{"name": name, "width": width, "height": height,
                            "pose_strategy": "source-bound four-view body and zone coverage",
                            "fov_deg": 90} for name, width, height in
                           (("overview", 1920, 1080), ("approach", 1280, 720),
                            ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))])
    (HERE / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    runner = (HERE / "runner.py").read_text()
    construction = {"law_id": "NRS-484B-110", "cell_id": "C10374", "actor": "motor_vehicle_driver",
                    "entrypoint": "runner.py", "status": "CPU delivery selected; original physical review pending",
                    "recording_description": primary["recording_description"],
                    "measurement_plan": ["source-bound moving body polygon and zone geometry at each original frame"],
                    "static_checks": ["exact selected cases", "four synchronized capture views", "600 frames at 20 Hz"],
                    "termination_rules": ["600 joined original Native frames", "abort on missing source or map designation"],
                    "mechanisms": ["source-shaped Native alley and zone geometry", "case-specific route request and fallback"],
                    "files": [{"path": "runner.py", "content": runner},
                              {"path": "config.json", "content": (HERE / "config.json").read_text()}]}
    (HERE / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")


if __name__ == "__main__":
    build()
