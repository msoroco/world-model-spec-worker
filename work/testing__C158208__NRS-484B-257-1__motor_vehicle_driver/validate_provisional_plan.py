"""Validate the 11-case source-planning chain without selecting delivery."""
from __future__ import annotations

import json
from pathlib import Path

from batch_pipeline import stages


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def validate() -> dict:
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    matrix = json.loads((HERE / "statutory-matrix.draft.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    proposals = json.loads((HERE / "proposals/cases.json").read_text())
    expected = set(matrix["accepted_recordings"])
    planned = {case["case_id"] for case in plan["cases"]}
    proposed = {case["case_id"] for case in proposals["cases"]
                if case["target_type"] != "baseline"}
    if expected != planned or expected != proposed:
        raise ValueError("statutory plan, canonical cases and accepted inventory disagree")
    comparisons = {row["comparison_id"]: row for row in plan["comparisons"]}
    for branch in matrix["branches"]:
        row = comparisons.get(branch["branch_id"])
        if row is None or set(row["case_ids"]) != set(branch["case_ids"]):
            raise ValueError("statutory branch lacks exact controlled comparison")
    template = json.loads((HERE / "proposals/template.json").read_text())
    for index, judgment in enumerate(template["structure"]["judgment_calls_needed"], 1):
        source = json.loads((HERE / "proposals" / f"judgment-{index}.json").read_text())
        judgment["observable_requirements"] = source["observable_requirements"]
    binding = json.loads((HERE / "proposals/bindings.json").read_text())
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    stages.validate("cases", proposals, {
        "request": {"cell": assignment["cell"], "actor": assignment["actor"]},
        "dependencies": [binding], "templates": [template],
        "canonical_parameter_rules": rules, "judgment_completion_policy": {},
    })
    return {"planned_cases": len(planned), "proposed_cases": len(proposed),
            "controlled_branches": len(matrix["branches"]),
            "source_grounded_sweeps_expanded": proposals.get("sweeps_expanded") is True}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
