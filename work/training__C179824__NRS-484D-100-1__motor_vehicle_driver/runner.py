"""Canonical CPU dispatch catalogue for the 13 exact Native case bundles.

The pinned runtime materializes each selected construction from execution-manifest.json.
This root entrypoint checks case identity and hands a local operator the exact
case entrypoint without inventing simulator observations.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def selected(case_id):
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    matches = [entry for entry in manifest["cases"] if entry["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("Unknown or duplicated exact Native case")
    entry = matches[0]
    construction = json.loads((ROOT / entry["construction"]).read_text())
    if construction["case_id"] != case_id:
        raise ValueError("Selected construction changed case")
    paths = {item["path"] for item in construction["files"]}
    if not {"runner.py", "config.json", entry["measurement_procedure"]["entrypoint"]} <= paths:
        raise ValueError("Selected Native implementation incomplete")
    return {"case_id": case_id, "construction": entry["construction"],
            "runner": "runner.py", "finalizer": entry["measurement_procedure"]["entrypoint"],
            "original_native_observed": False}


def check():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    config = json.loads((ROOT / "config.json").read_text())
    cases = [entry["case_id"] for entry in manifest["cases"]]
    if len(cases) != 13 or set(cases) != set(config["supported_case_ids"]):
        raise ValueError("Root Native catalogue does not cover all exact cases")
    for case in cases:
        selected(case)
    return {"selected_cases": len(cases), "original_native_observed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check() if args.check else selected(args.case), indent=2))
