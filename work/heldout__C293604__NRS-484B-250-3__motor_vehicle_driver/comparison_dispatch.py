"""Dispatch the linked opposing-left comparisons from sealed saved attempts.

The source auditors recompute measurements from original packets. This command
only selects an audit after checking the exact case identities and order.
"""

import argparse
import json
from pathlib import Path

from opposing_left_comparison_audit import audit as audit_intent
from shallow_turn_comparison_audit import audit as audit_shallow
from turn_release_sweep_audit import audit as audit_release

HERE = Path(__file__).resolve().parent


def dispatch(comparison_id, attempts, plan_path=HERE / "case-plan.json"):
    plan = json.loads(Path(plan_path).read_text())
    matches = [row for row in plan["comparisons"]
               if row["comparison_id"] == comparison_id]
    if len(matches) != 1:
        raise ValueError("Unknown or repeated comparison: " + comparison_id)
    cases = matches[0]["case_ids"]
    if len(attempts) != len(cases):
        raise ValueError("Comparison attempt count differs: " + comparison_id)
    paths = [Path(path) for path in attempts]
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("Comparison repeats a saved attempt")
    for case, path in zip(cases, paths):
        config = json.loads((path / "config.json").read_text())
        if config.get("selected_case_id") != case:
            raise ValueError("Saved attempt selects wrong exact case: " + case)
    if comparison_id == "opposing_left_intent_vs_making":
        result = audit_intent(*paths)
    elif comparison_id == "turn_release_delay_sweep":
        result = audit_release(paths)
    elif comparison_id == "opposing_left_shallow_vs_orthogonal":
        result = audit_shallow(*paths)
    else:
        raise ValueError("No source auditor for comparison: " + comparison_id)
    return {"format": "worker-linked-comparison-dispatch",
            "assignment_id": plan["assignment_id"],
            "comparison_id": comparison_id, "case_ids": cases,
            "source_audit": result, "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = dispatch(args.comparison, args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparison_id": args.comparison, "cases": len(result["case_ids"])}))


if __name__ == "__main__":
    main()
