"""Exact saved-attempt entrypoint for C125714's five controlled comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import audit_pair
from precedence_response_audit import audit_response_pair

SPECS = {
    "crossing_precedence": ("precedence", "advance", ("ego_response_request",)),
    "crossing_entry_order": ("advance", "other_later", ("entry_order",)),
    "opposite_intention": ("opposite_straight", "opposite_intends_left", ("left_turn_intent",)),
    "opposite_actual_left": ("opposite_intends_left", "opposite_makes_left", ("left_turn_realized",)),
    "separate_roadway_intersection": ("precedence", "wide_same_crossing",
                                      ("crossing_id", "roadway_id", "ego_approach_direction")),
}


def audit(comparison_id: str, left: Path, right: Path, *, diagnostic: bool = False) -> dict:
    if comparison_id not in SPECS:
        raise ValueError("unknown exact comparison")
    left_suffix, right_suffix, differences = SPECS[comparison_id]
    if Path(left).resolve() == Path(right).resolve():
        raise ValueError("comparison reuses one original attempt")
    if not diagnostic:
        for attempt, suffix in ((left, left_suffix), (right, right_suffix)):
            result = json.loads((Path(attempt) / "result.json").read_text())
            if result.get("case_id") != ROOT.name + "__" + suffix:
                raise ValueError("comparison selected another exact case: " + suffix)
    if comparison_id == "crossing_precedence":
        measured = audit_response_pair(left, right, diagnostic=diagnostic)
    else:
        measured = audit_pair(left, right, differences, diagnostic=diagnostic)
        measured = measured["comparison"]
    if measured.get("declared_differences") != sorted(differences):
        raise ValueError("comparison changed the declared differences")
    return {"format": "worker-exact-comparison-audit",
            "comparison_id": comparison_id,
            "case_ids": [ROOT.name + "__" + left_suffix,
                         ROOT.name + "__" + right_suffix],
            "declared_differences": sorted(differences),
            "measured": measured, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True, choices=tuple(SPECS))
    parser.add_argument("--left-attempt", type=Path, required=True)
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    receipt = audit(args.comparison_id, args.left_attempt, args.right_attempt,
                    diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(args.comparison_id + ": exact saved comparison audit passed")


if __name__ == "__main__":
    main()
