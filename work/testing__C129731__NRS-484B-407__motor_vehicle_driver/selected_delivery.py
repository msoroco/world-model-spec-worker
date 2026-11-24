"""Run the exact selected-original source review without canonical promotion.

All outputs are scratch artifacts. The command fails if any frozen original
video, trace, archived audit, sight source or full-decode proof is missing.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from delivery_audit import review
from original_source_acquisition import acquire
from saved_media_decode import decode_selected


def run(plan: dict, repository: Path, case_id: str, recording_id: str,
        sight_attempt: Path, source_bundle: Path, decode_receipt: Path,
        review_output: Path) -> dict:
    worker_root = Path(__file__).resolve().parents[2]
    scratch = worker_root / ".runtime-work"
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if not output_root.is_relative_to(scratch):
        raise ValueError("pipeline output root must be under .runtime-work")
    for path in (source_bundle, decode_receipt, review_output):
        if not Path(path).resolve().is_relative_to(scratch):
            raise ValueError("selected delivery outputs must be under .runtime-work")
        if Path(path).exists():
            raise ValueError("refusing to overwrite selected delivery output")
    inventory = json.loads((Path(sight_attempt) / "inventory.json").read_text())
    if (inventory.get("case_id") != case_id or
            inventory.get("recording_id") != recording_id):
        raise ValueError("selected sight attempt identity mismatch")
    acquire(plan, repository, case_id, recording_id, source_bundle)
    decode_selected(plan, repository, sight_attempt, source_bundle, decode_receipt)
    result = review(plan, repository, sight_attempt, source_bundle, decode_receipt)
    review_output = Path(review_output)
    review_output.parent.mkdir(parents=True, exist_ok=True)
    review_output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ("plan", "repository", "case", "recording", "sight-attempt",
                 "source-bundle", "decode-receipt", "review-output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    run(json.loads(Path(args.plan).read_text()), Path(args.repository), args.case,
        args.recording, Path(args.sight_attempt), Path(args.source_bundle),
        Path(args.decode_receipt), Path(args.review_output))


if __name__ == "__main__":
    main()
