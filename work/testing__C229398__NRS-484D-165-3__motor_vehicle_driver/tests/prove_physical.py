"""CPU fixture for parked-interval completion, with no physical claim."""

import argparse
import json
from pathlib import Path


def evaluate(case_id, outcome):
    if outcome == "complete_motion":
        rows = [{"time_s": index / 20, "speed_mps": 0.0, "hand_brake": True}
                for index in range(900)]
    elif outcome == "incomplete_motion":
        rows = [{"time_s": index / 20, "speed_mps": 0.0, "hand_brake": True}
                for index in range(450)]
    elif outcome == "missing_evidence":
        rows = []
    else:
        raise ValueError("unknown synthetic physical outcome")
    if not rows:
        status = "unverified"
    elif len(rows) != 900 or any(row["speed_mps"] > 0.25 or not row["hand_brake"]
                                 for row in rows):
        status = "not_met"
    else:
        status = "met"
    return {
        "case_id": case_id, "provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True, "maneuver_completed": status == "met",
        "physical_checks": {"maneuver": {
            "status": status, "method": "900 consecutive 20-Hz parked hand-brake and speed readbacks",
            "sources": ["synthetic fixture rows", "exact case configuration"]}},
        "realized_observables": {"sample_count": len(rows),
                                  "stationary_samples": sum(row["speed_mps"] <= 0.25
                                                            for row in rows)} if rows else {},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate(args.case, args.outcome)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "outcome": args.outcome,
                      "measured_status": result["physical_checks"]["maneuver"]["status"]}))
