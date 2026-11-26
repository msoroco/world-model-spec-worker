"""Independent pre-acceptance audit for an original posted-speed attempt.

The pinned media decoder and local acceptance still run separately. This stage
rejects missing original source and stale camera/trace references; it does not
turn accepted metadata or diagnostic fixture data into physical evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from speed_source_review import ASSIGNMENT, measure


MEDIA = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt: Path, inventory: dict, case_id: str) -> dict:
    attempt = Path(attempt).resolve()
    if case_id != inventory.get("case_id") or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("original delivery exact case mismatch")
    if inventory.get("diagnostic_fixture") is True:
        raise ValueError("diagnostic fixture cannot supply original delivery")
    result = measure(attempt, inventory, case_id)
    if inventory.get("source_kind") != "original_native":
        raise ValueError("original Native acquisition required")
    media = inventory.get("media")
    if not isinstance(media, dict) or set(media) != set(MEDIA) | {"trace"}:
        raise ValueError("complete four-view original media and trace inventory required")
    hashes = {}
    for name, entry in media.items():
        path = Path(entry.get("path", ""))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("original media path escapes attempt")
        target = (attempt / path).resolve()
        if not target.is_relative_to(attempt) or not target.is_file():
            raise ValueError("original media source missing: " + name)
        if target.stat().st_size == 0 or sha(target) != entry.get("sha256"):
            raise ValueError("original media source empty or stale: " + name)
        hashes[name] = entry["sha256"]
    if not all(media[name]["path"].endswith(".mkv") for name in MEDIA):
        raise ValueError("four original camera videos must be retained")
    if not media["trace"]["path"].endswith(".jsonl"):
        raise ValueError("original trace source must be retained")
    return {"format": "c136559-original-source-audit-v1", "case_id": case_id,
            "original_frames": result["original_frames"],
            "source_sha256": result["source_sha256"], "media_sha256": hashes,
            "governed_frames": result["governed_frames"],
            "observed_above_frames": result["observed_above_frames"],
            "physical_completion_confirmed": False,
            "full_video_decode_confirmed": False,
            "legal_applicability": "unresolved"}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite prior original source audit")
    inventory = json.loads((args.attempt / "inventory.json").read_text())
    result = audit(args.attempt, inventory, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
