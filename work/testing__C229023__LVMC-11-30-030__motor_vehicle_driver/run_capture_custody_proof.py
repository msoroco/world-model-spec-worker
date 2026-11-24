"""Recheck all diagnostic capture source packets and a changed-trace negative."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from saved_capture_audit import audit


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SCRATCH = Path(__file__).resolve().parents[2] / ".runtime-work" / "lead-nov24-converter"
SUFFIXES = (
    "unmarked_pass",
    "unmarked_other_stop_pass",
    "marked_pass",
    "unmarked_other_stop_wait",
    "unmarked_wait",
    "marked_wait",
)


def main() -> None:
    receipts = []
    for candidate in ("primary", "fallback1"):
        for suffix in SUFFIXES:
            if candidate == "primary":
                folder = "unmarked-pass-v4" if suffix == "unmarked_pass" else "compat-" + suffix
            else:
                folder = "fallback-unmarked-pass" if suffix == "unmarked_pass" else "fallback-" + suffix
            receipt = audit(directory=SCRATCH / folder, case_id=ASSIGNMENT + "__" + suffix, fixture_mode=True)
            receipts.append({"candidate_id": candidate, "case_id": receipt["case_id"],
                             "frame_count": receipt["frame_count"],
                             "first_native_frame": receipt["first_native_frame"],
                             "last_native_frame": receipt["last_native_frame"],
                             "trace_sha256": receipt["trace_sha256"],
                             "frame_map_sha256": receipt["frame_map_sha256"],
                             "physical_acceptance": receipt["physical_acceptance"]})
    with tempfile.TemporaryDirectory(prefix="capture-tamper-", dir=SCRATCH) as temp:
        negative = Path(temp)
        source = SCRATCH / "unmarked-pass-v4"
        for name in ("receipt.json", "context.json", "trace.jsonl", "frame-map.jsonl"):
            shutil.copyfile(source / name, negative / name)
        with (negative / "trace.jsonl").open("ab") as target:
            target.write(b"\n")
        try:
            audit(directory=negative, case_id=ASSIGNMENT + "__unmarked_pass", fixture_mode=True)
        except ValueError as error:
            if "changed original trace.jsonl bytes" not in str(error):
                raise
            negative_error = str(error)
        else:
            raise AssertionError("tampered trace was accepted")
    print(json.dumps({"format": "diagnostic-capture-custody-matrix", "assignment_id": ASSIGNMENT,
                      "passed": True, "diagnostic_fixture": True, "receipts": receipts,
                      "negative_error": negative_error, "physical_acceptance": "unverified",
                      "legal_judgment": "unresolved"}, indent=2))


if __name__ == "__main__":
    main()
