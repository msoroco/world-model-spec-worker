"""Draft exact railway selected cases without converting targets to outcomes."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    proposal = {"actor": plan["actor"], "cell_id": plan["cell_id"],
                "status": "draft", "sweeps_expanded": False,
                "cases": [], "sweep_specs": []}
    for case in plan["cases"]:
        key = case["case_id"].removeprefix(plan["assignment_id"] + "__")
        construction = json.loads((HERE / "cases" / key / "construction.json").read_text())
        differences = []
        paired = []
        for comparison in plan["comparisons"]:
            if case["case_id"] in comparison["case_ids"]:
                paired.append(comparison["comparison_id"])
                differences.extend(comparison["deliberate_differences"])
        proposal["cases"].append({
            "case_id": case["case_id"], "target_law_id": plan["law_id"],
            "target_type": "delivery", "rationale": case["branch"],
            "paired_probe_id": paired[0] if paired else None,
            "paired_probe_ids": paired,
            "deliberate_differences": list(dict.fromkeys(differences)),
            "variable_assignments": {
                "engineering_target_traversal_mph": case["engineering_target_traversal_mph"],
                "engineering_sight_setup": case["engineering_sight_setup"],
                "exception_setup": case["exception_setup"]},
            "unresolved_judgment_calls": [
                "Actual clear/unobstructed view and railway traffic scope need independent original review.",
                "Prima facie speed and statutory exception effects remain legal review calls."],
            "recording_description": construction["recording_description"],
        })
    proposal["sweep_specs"] = [{
        "sweep_id": "railway_sight_and_exception_review",
        "target_law_id": plan["law_id"], "status": "incomplete",
        "rationale": "No source-grounded legal visibility or traffic cutoff is supplied.",
        "missing_inputs": [
            "Independent source-grounded interpretation and physical visibility review."],
        "judgment_refs": [{"phrase": "clear and unobstructed view",
                           "note": "Original rays and images preserve facts; legal visibility remains unresolved."}]
    }]
    path = HERE / "proposals" / "cases.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"selected_cases": len(proposal["cases"]),
                      "source_bound_sweep_pending": True}))


if __name__ == "__main__":
    main()
