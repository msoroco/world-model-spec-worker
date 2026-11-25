"""Validate source-pending canonical proposals with pinned CPU stage contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def check() -> dict:
    from batch_pipeline import stages

    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    proposal_root = ROOT / "proposals"
    index = json.loads((proposal_root / "semantic-index.json").read_text())
    if index.get("format") != "worker-semantic-delivery" or index.get("assignment_id") != ROOT.name:
        raise ValueError("semantic index identity differs")
    for item in index.get("stages", {}).values():
        for ref in item if isinstance(item, list) else [item]:
            path = (ROOT / ref["path"]).resolve()
            if (not path.is_relative_to(proposal_root.resolve()) or not path.is_file() or
                    hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]):
                raise ValueError("semantic stage source hash differs")

    def read(name):
        return json.loads((proposal_root / (name + ".json")).read_text())

    law_id = assignment["law_id"]
    law = assignment["law"]
    request = {"cell": assignment["cell"], "actor": assignment["actor"]}
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    relevance = read("relevance")
    batch_relevance = read("relevance-batch")
    context = {"request": request, "law_records": {law_id: law}, "dependencies": []}
    stages.validate("relevance", relevance, context)
    stages.validate("relevance_batch", batch_relevance, context)
    if relevance != batch_relevance:
        raise ValueError("relevance stages differ")
    template = read("template")
    stages.validate("template", template, {"request": {"law_id": law_id,
                                                     "actor": assignment["actor"]},
                                          "law_record": law, "canonical_parameter_rules": rules,
                                          "dependencies": []})
    judgments = template["structure"]["judgment_calls_needed"]
    for index, expected in enumerate(judgments):
        stage = read("judgment-" + str(index))
        stages.validate("judgment_observables", stage,
                        {"request": {"template_id": template["template_id"],
                                     "phrase": expected["phrase"],
                                     "note": expected["note"]}, "dependencies": []})
        expected["observable_requirements"] = stage["observable_requirements"]
    binding = read("bindings")
    stages.validate("bindings", binding,
                    {"request": dict(request, template_ids=[template["template_id"]]),
                     "canonical_parameter_rules": rules, "dependencies": [template]})
    cases = read("cases")
    stages.validate("cases", cases,
                    {"request": request, "dependencies": [binding],
                     "templates": [template], "canonical_parameter_rules": rules,
                     "judgment_completion_policy": {}})
    if cases.get("sweeps_expanded") is not False or any(
            spec.get("status") != "incomplete" for spec in cases["sweep_specs"]):
        raise ValueError("original-source-dependent judgment sweeps must remain incomplete")
    return {"assignment_id": ROOT.name, "stage_contracts_passed": True,
            "selected_cases_planned": len(cases["cases"]) - 1,
            "comparisons_planned": len(cases["comparisons"]),
            "judgment_sweeps_pending_source": len(cases["sweep_specs"]),
            "delivery_ready": False}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
