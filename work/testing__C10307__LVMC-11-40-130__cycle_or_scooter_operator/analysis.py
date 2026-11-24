"""Saved-only selected bicycle speed and existing-condition finalizer.

Original sources are read through the SHA-bound acquisition inventory. This
report is descriptive and never decides reasonable or prudent speed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from speed_measurement import measure


ASSIGNMENT = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator"


def finalize(attempt: Path) -> dict:
    attempt = Path(attempt)
    for name in ("inventory.json", "frame-map.json", "bicycle-motion.json", "context.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__") or
            config.get("cell_id") != "C10307" or config.get("law_id") != "LVMC-11-40-130"):
        raise ValueError("saved bicycle case identity mismatch")
    inventory = json.loads((attempt / "inventory.json").read_text())
    measured = measure(attempt, inventory, case_id)
    if len(measured["samples"]) < 900:
        raise ValueError("Missing required source: full 900-frame original bicycle window")
    names = ("frame-map.json", "bicycle-motion.json", "context.json", "inventory.json")
    source_hashes = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest() for name in names}
    return {"format": "c10307-selected-bicycle-finalization-v1", "case_id": case_id,
            "measurements": {"actual_bicycle_speed_history": {"method": "measure_bicycle_speed",
                           "value": measured["samples"], "sources": source_hashes},
                             "contemporaneous_conditions": {"method": "measure_conditions",
                           "value": measured["condition_samples"], "sources": source_hashes}},
            "summary": measured["summary"], "source_sha256": source_hashes,
            "legal_prudence": "unresolved", "physical_acceptance": "unreviewed"}


def measure_bicycle_speed(attempt: Path) -> list:
    return finalize(attempt)["measurements"]["actual_bicycle_speed_history"]["value"]


def measure_conditions(attempt: Path) -> list:
    return finalize(attempt)["measurements"]["contemporaneous_conditions"]["value"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite saved bicycle finalization")
    report = finalize(args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
