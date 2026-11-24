"""Reprocess one saved exact-case attempt without a running simulator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_delivery import PREFIX, SUFFIXES, process_saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.case not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError("Foreign exact case")
    root = Path(__file__).resolve().parents[2]
    if (root / ".runtime-work" not in args.attempt.resolve().parents or
            root / ".runtime-work" not in args.output.resolve().parents):
        raise ValueError("Saved proof paths must be under .runtime-work")
    receipt = process_saved(args.attempt, args.output, allow_diagnostic=True)
    if receipt["case_id"] != args.case or receipt["source_audit"]["native_source"]:
        raise ValueError("Saved diagnostic receipt differs")
    print(json.dumps({"case_id": args.case,
                      "original_frames": receipt["source_audit"]["original_frame_count"],
                      "decoded_original_images": receipt["source_audit"]["decoded_original_images"],
                      "legal_necessity": receipt["legal_necessity"],
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
