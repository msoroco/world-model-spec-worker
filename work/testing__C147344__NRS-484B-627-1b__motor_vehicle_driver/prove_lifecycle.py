"""Exercise the diagnostic capture ownership state sequence.

This is a synthetic protocol test. It is not an owner release for an original
Native capture, and cannot be used as one.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reviewed_scene import ASSIGNMENT, VARIANTS

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--attempt", type=Path, required=True)
    p.add_argument("--saved-receipt", type=Path, required=True)
    a = p.parse_args()
    if a.case not in {ASSIGNMENT + "__" + s for s in VARIANTS}:
        raise ValueError("exact case required")
    provenance = json.loads((a.attempt / "acquisition-provenance.json").read_text())
    saved = json.loads(a.saved_receipt.read_text())
    if (provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True or
            saved.get("case_id") != a.case or not saved.get("passed") or
            not saved.get("recorded_only") or not saved.get("originals_preserved")):
        raise ValueError("synthetic saved-only lifecycle source invalid")
    print(json.dumps({"case_id": a.case, "scope": "synthetic lifecycle protocol only",
                      "events": EVENTS, "exit_code": 0, "original_owner_release_claimed": False},
                     sort_keys=True))


if __name__ == "__main__":
    main()
