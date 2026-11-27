"""Bind each exact narrow-highway case to a materialized source-gated bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SHARED_FILES = ("runner.py", "native_capture.py", "native_output_bridge.py",
                "highway_scene_construction.py", "highway_observations.py",
                "saved_finalizer.py", "comparison_audit.py", "delivery_audit.py",
                "analysis.py", "case-plan.json", "tests/test_highway_construction.py",
                "tests/test_comparison_audit.py", "tests/test_native_capture.py")


def write(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    primary = json.loads((ROOT / "config.json").read_text())
    recording = primary["case"]["recording_description"]
    for index, case in enumerate(plan["cases"]):
        variant = case["variant"]
        folder = ROOT if index == 0 else ROOT / "cases" / variant
        folder.mkdir(parents=True, exist_ok=True)
        config = dict(primary)
        config["selected_case_id"] = case["case_id"]
        config["case"] = {"case_id": case["case_id"], "recording_description": recording}
        config_path = folder / "config.json"
        write(config_path, config)
        materialized = []
        for name in SHARED_FILES:
            source = ROOT / name
            materialized.append({"path": name, "source": source.relative_to(REPO).as_posix(),
                                 "content": source.read_text()})
        materialized.append({"path": "config.json", "source": config_path.relative_to(REPO).as_posix(),
                             "content": config_path.read_text()})
        construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                        "actor": plan["actor"], "case_id": case["case_id"],
                        "entrypoint": "runner.py", "files": materialized,
                        "measurement_plan": {"case_id": case["case_id"],
                                             "legal_judgment": "unresolved",
                                             "procedure": "analysis.py",
                                             "source_packets": ["reviewed_highway_site", "original_context",
                                                                "original_trace", "original_camera_manifest"]},
                        "recording_description": recording,
                        "mechanisms": ["reviewed full highway geometry", "reviewed erected official no-parking device",
                                       "source-hashed Native operator", "four synchronized original cameras"],
                        "static_checks": ["exact assignment and plan hash", "reviewed original source hashes",
                                          "original 900 frame 20 Hz four-camera protocol"],
                        "termination_rules": ["stop on source hash or Native readback mismatch",
                                              "destroy owned Native actors"],
                        "status": "source_gated_incomplete"}
        write(folder / "construction.json", construction)
        disposition = plan["requirement_dispositions"][0]
        write(folder / "measurement-contract.json", {
            "format": "worker-measurement-contract", "case_id": case["case_id"],
            "requirements": [{"disposition_index": 0,
                              "requirement": disposition["requirement"],
                              "source": disposition["source"],
                              "kind": "measured", "method": "measure", "value_type": "object",
                              "output_key": "narrow_highway_device_and_parking",
                              "inputs": ["context.json", "original-trace.jsonl", "receipt.json", "cameras.json"]}],
            "negative": {"remove": ["context.json"],
                         "error_contains": "Missing required source: context.json"}})
    return len(plan["cases"])


if __name__ == "__main__":
    print(build())
