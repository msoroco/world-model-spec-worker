"""Check canonical school-lane draft stages against the pinned stage contracts."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def check():
    from batch_pipeline import stages

    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    root = HERE / "proposals"
    index = json.loads((root / "semantic-index.json").read_text())
    if index.get("format") != "worker-semantic-delivery" or index.get("assignment_id") != HERE.name:
        raise ValueError("school-lane semantic index identity differs")
    for item in index["stages"].values():
        for ref in item if isinstance(item, list) else [item]:
            path = (HERE / ref["path"]).resolve()
            if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError("school-lane semantic source hash differs")
    def read(name):
        return json.loads((root / (name + ".json")).read_text())
    law_id = assignment["law_id"]
    request = {"cell": assignment["cell"], "actor": assignment["actor"]}
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    relevance = read("relevance")
    context = {"request": request, "law_records": {law_id: assignment["law"]}, "dependencies": []}
    stages.validate("relevance", relevance, context)
    stages.validate("relevance_batch", read("relevance-batch"), context)
    template = read("template")
    stages.validate("template", template, {"request": {"law_id": law_id,
                                                     "actor": assignment["actor"]},
                                          "law_record": assignment["law"],
                                          "canonical_parameter_rules": rules, "dependencies": []})
    judgments = template["structure"]["judgment_calls_needed"]
    for i, expected in enumerate(judgments):
        stage = read("judgment-" + str(i))
        stages.validate("judgment_observables", stage,
                        {"request": {"template_id": template["template_id"],
                                     "phrase": expected["phrase"], "note": expected["note"]},
                         "dependencies": []})
        expected["observable_requirements"] = stage["observable_requirements"]
    binding = read("bindings")
    stages.validate("bindings", binding, {"request": dict(request, template_ids=[template["template_id"]]),
                                          "canonical_parameter_rules": rules, "dependencies": [template]})
    cases = read("cases")
    stages.validate("cases", cases, {"request": request, "dependencies": [binding],
                                    "templates": [template], "canonical_parameter_rules": rules,
                                    "judgment_completion_policy": {}})
    return {"assignment_id": HERE.name, "stage_contracts_passed": True,
            "selected_cases_planned": len(cases["cases"]) - 1,
            "comparisons_planned": len(cases["comparisons"]),
            "original_source_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
