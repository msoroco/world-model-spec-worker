"""Three source-bound synthetic motion outcomes for each exact case."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from emergency_scene import CASE_KNOBS
from physical_audit import assess_motion

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    args = parser.parse_args()
    suffix = args.case_id.removeprefix(HERE.name + "__")
    if suffix == args.case_id or suffix not in CASE_KNOBS:
        raise ValueError("Exact physical case required")
    capture = (REPO / ".runtime-work/c109035-delivery-proofs" /
               suffix / "positive/capture")
    if not capture.is_dir():
        raise ValueError("Saved original synthetic diagnostic source missing")
    rows = [json.loads(line) for line in (capture / "actor_trace.jsonl").read_text().splitlines()]
    site = json.loads((capture / "site_packet.json").read_text())
    if args.kind == "incomplete_motion":
        start = rows[0]["ego"]["x_m"]
        for row in rows:
            row["ego"]["x_m"] = start + (row["ego"]["x_m"] - start) * 0.25
    if args.kind == "missing_evidence":
        rows = None
    check = assess_motion(rows, site)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[args.kind]
    if check["status"] != expected:
        raise ValueError("Synthetic physical outcome differs: " + check["status"])
    result = {"case_id": args.case_id, "provenance_kind": "synthetic_fixture",
              "diagnostic_fixture": True, "maneuver_completed": expected == "met",
              "physical_checks": {"maneuver": check},
              "realized_observables": ({"approach_progress_m": {
                  "value": check["progress_m"], "unit": "m",
                  "method": check["method"], "source": "actor_trace.jsonl"}}
                  if expected == "met" else {}),
              "physical_acceptance_claimed": False}
    path = HERE / "physical" / suffix / (args.kind + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case_id, "kind": args.kind,
                      "status": expected, "result": str(path.relative_to(HERE))},
                     sort_keys=True))


if __name__ == "__main__":
    main()
