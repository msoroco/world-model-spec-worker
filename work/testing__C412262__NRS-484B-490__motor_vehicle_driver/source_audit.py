"""Inventory original sources without treating a conditional witness as proof."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = Path(__file__).resolve().parent.name
REQUIRED = {"highway_dedication_boundary_and_public_access": "highway-survey.json",
            "full_highway_width_profile": "width-survey.json",
            "official_device_erection_authority_content_conformity_extent": "device-survey.json",
            "responsible_person_vehicle_and_activity_purpose": "activity-source.json",
            "original_native_capture": "trace.jsonl"}


def audit(repo: Path) -> dict:
    source = repo / "inputs" / ASSIGNMENT
    assignment_path = source / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    if assignment.get("assignment_id") != ASSIGNMENT or assignment.get("cell_id") != "C412262":
        raise ValueError("frozen assignment identity changed")
    files = [p for p in source.rglob("*") if p.is_file()]
    names = {p.name for p in files}
    return {"assignment_id": ASSIGNMENT,
            "assignment_sha256": hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
            "accepted_recording_count": len(json.loads((source / "evidence.json").read_text()).get("recordings", [])),
            "missing_source_classes": [key for key, name in REQUIRED.items() if name not in names],
            "source_limit": ("The frozen export supplies a plausible ungrounded paved-road parking-device cell "
                             "and a conditional witness, but no reviewed public highway dedication, full boundary "
                             "and width survey, device authority/conformity/extent, activity purpose or original "
                             "Native motion. A synthetic sign or geometry cannot establish statutory facts.")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value)
    else:
        print(value, end="")


if __name__ == "__main__":
    main()
