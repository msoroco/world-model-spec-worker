"""Inventory immutable original street and notice sources for NRS 484B.493."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = Path(__file__).resolve().parent.name
REQUIRED = {"street_status_and_boundaries": "street-survey.json",
            "one_way_order_and_direction": "one-way-order.json",
            "official_notice_erection_content_extent": "notice-survey.json",
            "halt_purpose_and_activity": "activity-source.json",
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
            "accepted_metadata_count": sum(p.name == "metadata.json" and "accepted" in p.parts for p in files),
            "missing_source_classes": [key for key, name in REQUIRED.items() if name not in names],
            "source_limit": ("The frozen export gives a plausible ungrounded paved-road/parking-device cell "
                             "and conditional witness, but no reviewed one-way street order, official "
                             "notice authority/content/extent, activity purpose or original Native motion. "
                             "Synthetic geometry cannot establish legal street/device facts.")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding="utf-8")
    else:
        print(value, end="")


if __name__ == "__main__":
    main()
