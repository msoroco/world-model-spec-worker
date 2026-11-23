"""Worker proposal for validating a permission-only plain-rule case set.

This is a scoped draft for local review. The pinned semantic validator is unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PAIRS = {
    "second_lane_green_indication": (("adjacent_dark_drive", "second_green_drive"),
                                     "second_lane_green_request"),
    "green_permission_without_motion": (("green_selected_drive", "green_selected_stand"),
                                        "bus_motion_request"),
}


def validate(template, proposal, plan, assignment):
    if (template.get("law_id") != assignment["law_id"] or
            template.get("actor") != assignment["actor"] or
            template.get("quote") != assignment["law"]["text"] or
            template.get("structure", {}).get("obligation", {}).get("type") != "permission"):
        raise ValueError("exact permission template/source binding required")
    if template["structure"].get("judgment_calls_needed") or template["structure"].get("numeric_conditions"):
        raise ValueError("permission-only plain-rule scope required")
    prefix = assignment["assignment_id"] + "__"
    cases = {case["case_id"]: case for case in proposal["cases"] if case["target_type"] != "baseline"}
    expected = {prefix + kind for pair, _ in PAIRS.values() for kind in pair}
    if set(cases) != expected or any(c["target_law_id"] != assignment["law_id"] or
                                     c["target_type"] != "boundary_probe" for c in cases.values()):
        raise ValueError("permission boundary case identity/type mismatch")
    comparisons = {c["comparison_id"]: c for c in plan["comparisons"]}
    if set(comparisons) != set(PAIRS):
        raise ValueError("permission comparisons incomplete")
    for pair_id, (kinds, changed) in PAIRS.items():
        ids = [prefix + kind for kind in kinds]
        comp = comparisons[pair_id]
        if comp["case_ids"] != ids or not comp.get("fixed_conditions") or not comp.get("deliberate_differences"):
            raise ValueError("permission comparison pair or controls missing")
        first, second = (cases[ident] for ident in ids)
        if first.get("paired_probe_id") != pair_id or second.get("paired_probe_id") != pair_id:
            raise ValueError("permission probe link missing")
        a = {key: value["value"] for key, value in first["variable_assignments"].items()}
        b = {key: value["value"] for key, value in second["variable_assignments"].items()}
        if set(a) != set(b) or {key for key in a if a[key] != b[key]} != {changed}:
            raise ValueError("permission comparison changes an undeclared variable")
    if any(c.get("legal_judgment") != "unresolved" or c.get("physical_acceptance_claimed") is not False
           for c in plan["cases"]):
        raise ValueError("permission planning claims unreviewed outcome")
    return {"format": "worker-permission-semantic-proposal-proof", "assignment_id": assignment["assignment_id"],
            "pair_ids": sorted(PAIRS), "case_ids": sorted(expected), "legal_verdict_claimed": False,
            "scope": "Worker-only permission boundary proof; pinned semantic validator unchanged"}


def main():
    template = json.loads((ROOT / "proposals/template.json").read_text())
    cases = json.loads((ROOT / "proposals/cases.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    report = validate(template, cases, plan, assignment)
    report["source_sha256"] = hashlib.sha256((REPO / "inputs" / ROOT.name / "assignment.json").read_bytes()).hexdigest()
    (ROOT / "proposals/permission-semantic-proposal-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print("worker-only permission semantic proposal passed; pinned runtime remains unchanged")


if __name__ == "__main__":
    main()
