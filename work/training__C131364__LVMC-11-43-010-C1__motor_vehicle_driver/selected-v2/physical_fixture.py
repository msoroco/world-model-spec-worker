"""CPU-only classifier fixtures for the exact 600-frame roundabout cases."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def classify(case, kind):
    assert case in {ROOT.name + "__witness_1", ROOT.name + "__witness_2"}
    assert kind in {"complete_motion", "incomplete_motion", "missing_evidence"}
    # These rows model source availability and route completion. They are never
    # presented as an original CARLA capture or a legal conclusion.
    evidence = {
        "complete_motion": (600, [10, 11, 12]),
        "incomplete_motion": (600, [10, 11]),
        "missing_evidence": (0, []),
    }
    frames, observed_roads = evidence[kind]
    status = ("unverified" if not frames else
              "met" if observed_roads == [10, 11, 12] else "not_met")
    return {
        "format": "c131364-physical-completion-cpu-fixture",
        "case_id": case,
        "fixture_kind": kind,
        "provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True,
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "CPU fixture road-sequence and frame-availability classification",
            "sources": ["synthetic 600-frame source availability and road sequence"],
        }},
        "maneuver_completed": status == "met",
        "realized_observables": ({"fixture_frames": frames,
                                  "fixture_observed_road_sequence": observed_roads}
                                 if status == "met" else {}),
        "physical_acceptance_claimed": False,
        "legal_verdict": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result = classify(args.case, args.kind)
    Path(args.result).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case, "kind": args.kind,
                      "status": result["physical_checks"]["maneuver"]["status"],
                      "fixture_only": True}))
