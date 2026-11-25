"""Audit frozen original-source availability without inferring accepted coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C144550__NRS-484B-223-1b__motor_vehicle_driver"
REQUIRED = ("trace.jsonl", "video_frames.jsonl", "overview.mkv",
            "approach.mkv", "reference_corner.mkv", "driver_reference.mkv",
            "original-driver-input.jsonl")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(repo: Path) -> dict:
    source = repo / "inputs" / ASSIGNMENT
    evidence_path = source / "evidence.json"
    evidence = json.loads(evidence_path.read_text())
    rows = []
    for entry in evidence["recordings"]:
        rid = entry["recording_id"]
        accepted = source / "accepted" / rid
        metadata = accepted / "metadata.json"
        listed = entry["sources"]
        if len(listed) != 1 or listed[0]["sha256"] != sha(metadata):
            raise ValueError("frozen accepted metadata SHA256 differs: " + rid)
        original = {name: sha(accepted / name) for name in REQUIRED
                    if (accepted / name).is_file() and not (accepted / name).is_symlink()}
        rows.append({"recording_id": rid, "metadata_sha256": sha(metadata),
                     "available_original_source_hashes": original,
                     "missing_required_original_sources": [name for name in REQUIRED
                         if name not in original],
                     "law_coverage_verified": False,
                     "reuse_selected": False})
    return {"format": "c144550-original-source-availability-v1",
            "assignment_id": ASSIGNMENT, "evidence_sha256": sha(evidence_path),
            "accepted_sources": rows,
            "conclusion": "Frozen acceptance metadata alone cannot establish either conjunctive prerequisite or controlled comparison."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.repo)
    if args.output.exists():
        raise ValueError("source availability receipt already exists")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
