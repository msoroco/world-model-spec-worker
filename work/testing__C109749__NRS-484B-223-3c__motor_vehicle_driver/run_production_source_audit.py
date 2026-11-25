"""Audit a closed original Native attempt without altering its sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_finalizer import finalize_saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.attempt.resolve().name != "original-attempt":
        raise ValueError("Original Native attempt directory required")
    result = finalize_saved(args.attempt, args.case, 900)
    if result["decoded_camera_images"] != 3600:
        raise ValueError("Production audit needs all original camera pixels")
    result["source_audit_passed"] = True
    result["physical_acceptance_claimed"] = False
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": args.case, "decoded_camera_images": 3600,
                      "source_audit_passed": True}))


if __name__ == "__main__":
    main()
