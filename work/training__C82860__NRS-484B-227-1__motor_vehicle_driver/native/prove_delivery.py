"""Test independent saved-source audit with diagnostic and rejection modes."""

import argparse
import json
import tempfile
from pathlib import Path

from delivery_audit import audit
from finalize import finalize
from test_measure_uturn import fixture


def prove(case_id, negative):
    suffix = case_id.rsplit("__", 1)[-1]
    if suffix not in ("authorized_opening", "barrier_crossing"):
        raise ValueError("Unknown exact U-turn case")
    with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
        attempt = Path(temp)
        fixture(attempt, suffix)
        (attempt / "config.json").write_text(json.dumps({"selected_case_id": case_id}) + "\n")
        (attempt / "construction.json").write_text(json.dumps({
            "case_id": case_id, "recording_description": "Synthetic source test"}) + "\n")
        (attempt / "trace.jsonl").write_text('{"time_s":0}\n')
        (attempt / "body_history.jsonl").write_text('{"frame":0}\n')
        (attempt / "capture").mkdir()
        (attempt / "capture/evidence.jsonl").write_text('{"frame":0}\n')
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            (attempt / (name + ".mkv")).write_bytes(b"diagnostic-placeholder")
        report = attempt / "analysis-report.json"
        finalize(attempt, report)
        if negative:
            audit(attempt, report, diagnostic=False)
            raise AssertionError("Synthetic fixture passed original-source audit")
        result = audit(attempt, report, diagnostic=True)
        if result["case_id"] != case_id or not result["source_joins_passed"] or result["original_native_gate_checked"]:
            raise AssertionError("Diagnostic source audit did not verify exact case")
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    prove(args.case, args.negative)
