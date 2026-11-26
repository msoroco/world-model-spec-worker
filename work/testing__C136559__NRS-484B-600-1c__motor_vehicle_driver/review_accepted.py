"""Bind retained accepted metadata to original source review, without relabeling it."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from original_source_audit import audit


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def review(original_attempt: Path, case_id: str) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    candidates = [case for case in plan["cases"] if case["case_id"] == case_id]
    if len(candidates) != 1:
        raise ValueError("exact accepted case missing from plan")
    candidate = candidates[0]
    recording_id = candidate.get("recording_id")
    metadata_path = REPO / "inputs" / ROOT.name / "accepted" / recording_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("recording_id") not in (None, recording_id) or metadata.get("case_id") != case_id:
        raise ValueError("accepted metadata and exact case mismatch")
    inventory_path = original_attempt / "inventory.json"
    if not inventory_path.is_file():
        raise ValueError("original accepted Native source inventory missing")
    inventory = json.loads(inventory_path.read_text())
    if inventory.get("recording_id") != recording_id:
        raise ValueError("original recording identity differs from accepted metadata")
    source_receipt = audit(original_attempt, inventory, case_id)
    return {"format": "c136559-retained-accepted-source-review-v1",
            "case_id": case_id, "recording_id": recording_id,
            "accepted_metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
            "original_inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
            "source_audit": source_receipt,
            "existing_acceptance_relabelled": False,
            "law_coverage_confirmed": False,
            "full_video_decode_confirmed": False,
            "legal_applicability": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite accepted source review")
    receipt = review(args.original_attempt, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
