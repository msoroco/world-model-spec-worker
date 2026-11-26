"""All seven comparisons with fixed-source and declared-difference rejects."""

from copy import deepcopy
import json
from pathlib import Path

from audit_diagnostic_comparisons import audit, record
from prove_statutory_measurement import packet


def rejects(comparison, records, fragment, require_original=False):
    try:
        audit(comparison, records, require_original=require_original)
    except ValueError as error:
        if fragment not in str(error):
            raise AssertionError(str(error)) from error
        return
    raise AssertionError("Invalid comparison passed")


def main():
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder / "case-plan.json").read_text())
    saved = {}
    for case in plan["cases"]:
        slug = case["case_id"].removeprefix(plan["assignment_id"] + "__")
        context, rows = packet(slug)
        saved[case["case_id"]] = record(context, rows, case["case_id"])
    for comparison in plan["comparisons"]:
        records = {cid: deepcopy(saved[cid]) for cid in comparison["case_ids"]}
        proof = audit(comparison, records, require_original=False)
        assert proof["fixed_source_checks_passed"] and proof["legal_verdict"] is None
        rejects(comparison, records, "Original Native source", require_original=True)
        short = comparison["comparison_id"].split("__")[-1]
        changed = deepcopy(records)
        last = comparison["case_ids"][-1]
        if short == "comparison":
            changed[last]["through_motion_sha256"] = "0" * 64
            expected = "Through-highway motion changed"
        elif short == "yield_sign_action":
            changed[last]["observation"]["source_hashes"]["reference"] = "0" * 64
            expected = "Stopping reference changed"
        elif short in {"stopping_reference", "yield_reference"}:
            changed[last]["static_facts"]["sign_kind"] = "wrong-sign"
            expected = "Fixed source changed: sign_kind"
        elif short == "through_vehicle_phase":
            changed[last]["ego_motion_sha256"] = "0" * 64
            expected = "Through-vehicle phase isolation"
        elif short == "crossing_interval":
            changed[last]["through_motion_sha256"] = next(iter(records.values()))["through_motion_sha256"]
            expected = "Through-vehicle phase isolation"
        else:
            changed[last]["observation"]["source_hashes"]["controls"] = next(iter(records.values()))["observation"]["source_hashes"]["controls"]
            expected = "Controlling exception isolation"
        rejects(comparison, changed, expected)
    print("eight source-shaped comparisons pass; eight fixed/difference and eight original-source negatives pass")


if __name__ == "__main__":
    main()
