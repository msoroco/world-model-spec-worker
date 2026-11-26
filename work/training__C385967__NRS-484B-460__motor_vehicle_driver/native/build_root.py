"""Materialize assignment-root dispatch artifacts from selected primary A."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent


def build():
    construction = json.loads((HERE / "selected-a-construction.json").read_text())
    construction["measurement_plan"] = {
        "method": "source-joined Native/device/curb/body/camera angle measurement",
        "inputs": ["native_samples.jsonl", "body_history.jsonl", "video_frames.jsonl",
                   "official_device.json", "road_geometry.json", "parking_context.json"]}
    construction["static_checks"] = ["exact case identity", "600 frames at 20 Hz",
        "four source cameras", "authored 45-degree device and governed highway bay"]
    construction["termination_rules"] = ["complete 600 Native frames",
        "close all encoders and restore world before saved processing"]
    construction["mechanisms"] = {"native_source": "capture.py",
        "saved_source_measurement": "finalize.py",
        "physical_status": "original Native unverified"}
    (FOLDER / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    for item in construction["files"]:
        destination = FOLDER / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(item["content"])
    config = json.loads((FOLDER / "config.json").read_text())
    config["supported_case_ids"] = [FOLDER.name + "__selected_03f318de__" + suffix +
                                    "condition_" + x
                                    for suffix in ("", "stop_", "stand_") for x in "ab"]
    # The root config is a dispatch index; its selected file remains the exact case A source.
    (FOLDER / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    for item in construction["files"]:
        if item["path"] == "config.json":
            item["content"] = (FOLDER / "config.json").read_text()
    (FOLDER / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    print(json.dumps({"root_case": construction["case_id"],
                      "supported_cases": config["supported_case_ids"]}, sort_keys=True))


if __name__ == "__main__":
    build()
