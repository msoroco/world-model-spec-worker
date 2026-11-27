"""CPU physical outcome classification from source-bound diagnostic motion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bridge_observations import measure_crossing, verify_site_bundle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    site_path = attempt / "bridge-site.json"
    trace_path = attempt / "original-motion.jsonl"
    marker_path = attempt / "fixture-provenance.json"
    if not marker_path.is_file() or not json.loads(marker_path.read_text()).get("scope", "").startswith("CPU diagnostic"):
        raise ValueError("physical CPU probe requires explicit synthetic diagnostic provenance")
    sources = {path.name: sha(path) for path in (site_path, trace_path, marker_path) if path.is_file()}
    check = {"status": "unverified", "method": "source-joined original station crossing assessment",
             "sources": sources, "intervals": [], "physical_causation_claimed": False,
             "legal_verdict_claimed": False}
    observed = {}
    try:
        if not site_path.is_file():
            raise ValueError("Missing required source: bridge-site.json")
        if not trace_path.is_file():
            raise ValueError("Missing required source: original-motion.jsonl")
        site = verify_site_bundle(site_path, sha(site_path), case_id)
        rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
        try:
            measured = measure_crossing(site, rows, case_id, expected_frames=9)
        except ValueError as error:
            check["status"] = "not_met"
            check["details"] = {"reason": str(error), "original_frame_count": len(rows)}
        else:
            check["status"] = "met"
            check["details"] = {"crossing_original_frames": measured["crossing_original_frames"],
                                "observed_crossing_speed_mph": measured["observed_crossing_speed_mph"],
                                "original_frame_count": measured["original_frame_count"]}
            observed = {"diagnostic_crossing_speed_mph": measured["observed_crossing_speed_mph"],
                        "diagnostic_sign_offsets_ft": measured["sign_offsets_ft"]}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        check["details"] = {"reason": str(error)}
    return {"case_id": case_id, "physical_checks": {"maneuver": check},
            "maneuver_completed": check["status"] == "met",
            "realized_observables": observed,
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = assess(args.attempt, args.case)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(result["physical_checks"]["maneuver"]["status"])


if __name__ == "__main__":
    main()
