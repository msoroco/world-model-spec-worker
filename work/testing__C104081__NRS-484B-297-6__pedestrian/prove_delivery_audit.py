"""Exercise original-source review on labeled CPU fixtures for one exact case.

The positive fixture models a source-complete Native acquisition; its pixel
decoder is mocked, so this proof never asserts that an actual source exists.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from test_original_review import OriginalReviewTests
from delivery_audit import audit_delivery


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if not args.case.startswith(ROOT.name + "__"):
        raise ValueError("exact assignment case required")
    os.environ["C104081_PROOF_CASE"] = args.case
    fixture = OriginalReviewTests("test_reviewed_original_bytes_and_participant_census")
    fixture.setUp()
    try:
        if args.negative:
            fixture.saved_audit["source_kind"] = "synthetic_fixture"
        with patch("delivery_audit.audit_saved", return_value=fixture.saved_audit), \
                patch("original_review._decoded_frame_hashes",
                      return_value={frame: "a" * 64 for frame in fixture.sample_frames}):
            receipt = audit_delivery(fixture.root, args.case, fixture.review)
        if not all(receipt["checks"].values()):
            raise ValueError("CPU original-review fixture check incomplete")
        print("synthetic CPU original-review fixture passed:", args.case)
        print("actual source pixels and physical acceptance remain unverified")
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
