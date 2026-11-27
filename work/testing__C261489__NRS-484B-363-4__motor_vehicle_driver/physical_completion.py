"""Source-based physical completion classifier for synthetic CPU outcome probes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from school_pass import ASSIGNMENT, case_name, measure_original

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
from test_school_pass import rows, scene


def sha_rows(value: list[dict]) -> str:
    raw = "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in value) + "\n"
    return hashlib.sha256(raw.encode()).hexdigest()


def assess(case_id: str, kind: str) -> dict:
    name = case_name(case_id)
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unknown physical fixture kind")
    site = scene(name)
    original = rows(site)
    if kind == "incomplete_motion":
        if name == "no_pass":
            for index, row in enumerate(original):
                row["ego_route_progress_m"] = row["target_route_progress_m"] + (index - 400) / 20
                row["lateral_separation_m"] = 2.0
        else:
            for row in original:
                row["ego_route_progress_m"] = row["target_route_progress_m"] - 5
    if kind == "missing_evidence":
        del original[150]["map_geometry_source_sha256"]
    sources = {"original-trace.jsonl": sha_rows(original),
               "context.json": hashlib.sha256(json.dumps(site, sort_keys=True).encode()).hexdigest()}
    status = "unverified"
    reason = "required original source absent"
    observed = {}
    try:
        measured = measure_original(original, site, case_id)
    except ValueError as error:
        reason = str(error)
        if kind != "missing_evidence":
            status = "not_met"
    else:
        status = "met"
        reason = "case-specific 900-frame source-bound maneuver criterion met"
        observed = {"diagnostic_motion": measured}
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if status != expected:
        raise ValueError("physical fixture classifier did not distinguish " + kind)
    return {"format": "worker-physical-outcome-fixture", "assignment_id": ASSIGNMENT,
            "case_id": case_id, "fixture_kind": kind, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {"status": status,
                "method": "school_pass.measure_original on 900 case-specific synthetic frames",
                "sources": sources, "reason": reason,
                "legal_verdict_claimed": False}},
            "realized_observables": observed,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(assess(args.case, args.kind), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
