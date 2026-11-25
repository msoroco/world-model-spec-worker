"""Saved-only exact-case original motion/relation finalization.

This never starts CARLA, edits acquisition, or infers legal impediment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from finalize_follower import finalize
from reviewed_scene import ASSIGNMENT, VARIANTS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process(attempt: Path, output: Path, case_id: str, diagnostic_fixture=False) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact selected case required")
    if output.exists() or output.is_relative_to(attempt) or attempt.is_relative_to(output):
        raise ValueError("fresh derived output outside original acquisition required")
    trace, relation = attempt / "trace.json", attempt / "relation.json"
    for path in (trace, relation):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    trace_sha, relation_sha = sha(trace), sha(relation)
    trace_data = json.loads(trace.read_text(encoding="utf-8"))
    if bool(trace_data.get("diagnostic_fixture")) != bool(diagnostic_fixture):
        raise ValueError("original versus diagnostic source provenance mismatch")
    measurement = finalize(trace, trace_sha, relation, relation_sha, case_id)
    if sha(trace) != trace_sha or sha(relation) != relation_sha:
        raise ValueError("saved processing changed original acquisition")
    output.mkdir(parents=True)
    (output / "measurement.json").write_text(json.dumps(measurement, indent=2) + "\n", encoding="utf-8")
    receipt = {"format": "c147344-recorded-only-processing-v1", "case_id": case_id,
               "source_kind": "synthetic_software_fixture" if diagnostic_fixture else "original_native_attempt",
               "trace_sha256": trace_sha, "relation_sha256": relation_sha,
               "measurement_sha256": sha(output / "measurement.json"),
               "original_frame_count": measurement["original_frame_count"],
               "analysis_complete": True, "legal_verdict_claimed": False,
               "delivery_ready": False}
    (output / "processing-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(process(args.attempt, args.output, args.case, args.diagnostic_fixture), sort_keys=True))


if __name__ == "__main__":
    main()
