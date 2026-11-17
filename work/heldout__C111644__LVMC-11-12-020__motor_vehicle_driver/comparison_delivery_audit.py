"""Audit declared turn-course comparisons from retained original sources."""

import argparse
import json
from pathlib import Path

from indication_form_audit import audit as audit_forms
from turn_marking import audit_saved_turn_route_response


ROUTE_FORMS = {
    "marker_route_response": "marker",
    "button_route_response": "button",
    "other_indication_route_response": "other_indication",
}


def audit(comparison, attempts):
    if comparison in ROUTE_FORMS:
        if len(attempts) != 2:
            raise ValueError("Route comparison requires exactly two attempts")
        form = ROUTE_FORMS[comparison]
        result = audit_saved_turn_route_response(*map(Path, attempts))
        left = json.loads((Path(attempts[0]) / "config.json").read_text())
        right = json.loads((Path(attempts[1]) / "config.json").read_text())
        if (not left["selected_case_id"].endswith("__" + form + "_follow") or
                not right["selected_case_id"].endswith("__" + form + "_depart")):
            raise ValueError("Comparison selected another indication form or route order")
        if not result["comparison_complete"] or not result["source_joined"]:
            raise ValueError("Route comparison lacks original-source join")
        case_ids = [left["selected_case_id"], right["selected_case_id"]]
        findings = result
    elif comparison == "indication_form":
        if len(attempts) != 3:
            raise ValueError("Form comparison requires exactly three attempts")
        findings = audit_forms(attempts)
        if findings["comparison_id"] != comparison or not findings["fixed_conditions_verified"]:
            raise ValueError("Form comparison lacks fixed-condition proof")
        case_ids = findings["case_ids"]
    else:
        raise ValueError("Unknown declared comparison")
    return {"format": "worker-turn-comparison-delivery-audit",
            "comparison_id": comparison, "case_ids": case_ids,
            "fixed_conditions_checked": True,
            "declared_difference_checked": True,
            "findings": findings,
            "diagnostic_fixture": True,
            "municipal_authorization_verified": False,
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.comparison, args.attempt)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("comparison_delivery_audit_passed", args.comparison, len(result["case_ids"]))
