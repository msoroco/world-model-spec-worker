"""Inventory the immutable school site and timing sources before dispatch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = Path(__file__).resolve().parent.name
REQUIRED = {"crossing_zone_site": "crossing-zone-site.json",
            "school_calendar": "school-calendar.json",
            "operation_and_class_schedule": "school-schedule.json",
            "local_clock": "local-clock.json",
            "beacon_and_sign": "beacon-sign-survey.json",
            "original_native_capture": "trace.json"}


def audit(repo: Path) -> dict:
    source = repo / "inputs" / ASSIGNMENT
    path = source / "assignment.json"
    assignment = json.loads(path.read_text())
    if assignment.get("assignment_id") != ASSIGNMENT or assignment.get("cell_id") != "C255863":
        raise ValueError("frozen school-zone assignment changed")
    files = [p for p in source.rglob("*") if p.is_file()]
    names = {p.name for p in files}
    accepted = [p for p in files if p.name == "metadata.json" and "accepted" in p.parts]
    return {"assignment_id": ASSIGNMENT,
            "assignment_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "accepted_metadata_count": len(accepted),
            "missing_source_classes": [key for key, name in REQUIRED.items() if name not in names],
            "source_limit": ("Frozen inputs contain the law/cell and conditional witness, but no "
                             "reviewed crossing-zone geometry, school calendar or schedule, local time, "
                             "beacon/sign state or original Native motion. These cannot be inferred "
                             "from synthetic 900-frame fixtures.")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.repo.resolve())
    value = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding="utf-8")
    else:
        print(value, end="")


if __name__ == "__main__":
    main()
