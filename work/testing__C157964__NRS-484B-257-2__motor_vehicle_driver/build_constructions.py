"""Rebuild the three exact, inline subsection 2 Native constructions."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from officer_direction import PREFIX, SUFFIXES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE_NAMES = ["runner.py", "finalizer.py", "comparison_audit.py", "delivery_audit.py", "officer-site.xodr"] + [
    path.name for path in sorted(ROOT.glob("officer_*.py"))
]
TEST_NAMES = ["tests/" + path.name for path in sorted((ROOT / "tests").glob("test*.py"))]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def construction(case_id, config_path):
    config = json.loads(config_path.read_text())
    if config["selected_case_id"] != case_id or config["case"]["case_id"] != case_id:
        raise ValueError("Exact officer construction config mismatch")
    files = []
    for name in SOURCE_NAMES + TEST_NAMES:
        source = ROOT / name
        files.append({"path": name, "source": source.relative_to(REPO).as_posix(),
                      "content": source.read_text()})
    files.append({"path": "config.json", "source": config_path.relative_to(REPO).as_posix(),
                  "content": config_path.read_text()})
    return {
        "case_id": case_id,
        "law_id": config["law_id"], "cell_id": config["cell_id"], "actor": config["actor"],
        "entrypoint": "runner.py", "status": "draft",
        "recording_description": config["recording_description"],
        "measurement_plan": {
            "raw_sources": ["source_review/source-packet.json", "source_review/officer-site.xodr",
                            "capture-receipt.json", "capture/evidence.jsonl", "trace.jsonl",
                            "video_frames.jsonl"] + [name + ".mkv" for name in
                                                      ("overview", "approach", "reference_corner", "driver_reference")],
            "analysis_entrypoint": "finalizer.py",
            "saved_processing_status": "saved-only finalizer authored; full compatibility pending",
        },
        "files": files,
        "static_checks": [
            "Authored signed one-way-to-two-way junction and both other approach lanes validated",
            "Exact case, 600 frames and original four-camera profile validated offline",
            "Six source files and 600-frame hazard plan hash checked before Native tick",
        ],
        "termination_rules": [
            "Exactly 600 source and graph frames at 20 Hz or fail",
            "Close graph recorder before actor destruction and seal after camera encoders and world restoration",
            "Never replace requested officer direction with claimed observed direction",
        ],
        "mechanisms": [
            "Generate source-bound OpenDRIVE signed non-through entrance and two-way crossing",
            "Spawn ego, other vehicle and officer performer with explicit Native blueprints and transforms",
            "Apply and read back officer arm direction and ego/other vehicle controls",
            "Record four original lossless camera streams, bodies, graph and original frame map",
        ],
        "source_packets": [],
        "case": config["case"],
        "physical_completion": config["physical_completion"],
        "supported_case_ids": config["supported_case_ids"],
    }


def main():
    root_config = json.loads((ROOT / "config.json").read_text())
    case_ids = [PREFIX + suffix for suffix in SUFFIXES]
    if set(root_config["supported_case_ids"]) != set(case_ids):
        raise ValueError("Three-case support set mismatch")
    for index, case_id in enumerate(case_ids):
        if index == 0:
            config_path = ROOT / "config.json"
            construction_path = ROOT / "construction.json"
        else:
            case_dir = ROOT / "cases" / case_id
            config_path = case_dir / "config.json"
            config = dict(root_config)
            config["selected_case_id"] = case_id
            config["case"] = dict(root_config["case"], case_id=case_id)
            if case_id.endswith("__officer_controls_hold"):
                config["physical_completion"] = dict(
                    root_config["physical_completion"],
                    body_key="other_body_vertices_xy_m", exit_axis=1,
                )
            write_json(config_path, config)
            construction_path = case_dir / "construction.json"
        write_json(construction_path, construction(case_id, config_path))
        print(case_id, hashlib.sha256(construction_path.read_bytes()).hexdigest())
        fallback_config = deepcopy(json.loads(config_path.read_text()))
        fallback_config["camera_mounts"]["overview"]["pose"]["location"].update(
            {"x": -4.0, "y": -2.0, "z": 22.0})
        fallback_config["camera_mounts"]["overview"]["pose"]["rotation"].update(
            {"yaw": -145.0, "pitch": -60.0})
        fallback_config["camera_mounts"]["reference_corner"]["pose"]["location"].update(
            {"x": -9.0, "y": -10.0, "z": 10.0})
        fallback_config["camera_mounts"]["reference_corner"]["pose"]["rotation"].update(
            {"yaw": 35.0, "pitch": -30.0})
        fallback_dir = ROOT / "cases" / case_id / "fallback1"
        fallback_path = fallback_dir / "config.json"
        write_json(fallback_path, fallback_config)
        fallback_construction = fallback_dir / "construction.json"
        write_json(fallback_construction, construction(case_id, fallback_path))
        print(case_id, "fallback1", hashlib.sha256(fallback_construction.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
