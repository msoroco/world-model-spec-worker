"""Saved-only crosswalk analysis for an exact original attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crosswalk_finalizer import finalize

SOURCES = ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json",
           "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def measure_crosswalk_observation(finalized: dict) -> dict:
    measured = finalized["measured_values"]
    observed = finalized["observed"]
    if not isinstance(measured, dict) or not isinstance(observed, dict):
        raise ValueError("original crosswalk measurement required")
    return {"measured_values": measured, "observed": observed,
            "target_checks": finalized["target_checks"],
            "legal_judgment": "unresolved"}


def run(attempt: str | Path, output: str | Path, case_id: str) -> dict:
    root = Path(attempt).resolve()
    target = Path(output).resolve()
    if not root.is_dir() or target.parent != root or target.name != "analysis-report.json":
        raise ValueError("analysis report must be inside the saved original attempt")
    if target.exists():
        raise ValueError("retain prior analysis report")
    hashes = {}
    for name in SOURCES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing required source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    finalized = finalize(directory=root, case_id=case_id)
    if finalized.get("case_id") != case_id:
        raise ValueError("saved finalizer returned another exact case")
    if any(hashlib.sha256((root / name).read_bytes()).hexdigest() != digest
           for name, digest in hashes.items()):
        raise ValueError("saved analysis changed original source")
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"crosswalk_observation": {
                  "value": measure_crosswalk_observation(finalized),
                  "method": "measure_crosswalk_observation", "sources": hashes}},
              "analysis_complete": True, "source_hashes": hashes,
              "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    case_id = args.case
    if case_id is None:
        config = Path(args.attempt) / "config.json"
        if not config.is_file():
            raise ValueError("exact materialized case config required")
        case_id = json.loads(config.read_text())["selected_case_id"]
    print(json.dumps(run(args.attempt, args.output, case_id), sort_keys=True))


if __name__ == "__main__":
    main()
