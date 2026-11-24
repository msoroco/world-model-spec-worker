"""Validate source-bound draft semantic stages against the pinned runtime."""
from __future__ import annotations

import json
import hashlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def validate() -> None:
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not output or not Path(output).resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import")
    sys.path.insert(0, str((REPO / "runtime/scenario_pipeline").resolve()))
    from batch_pipeline import stages

    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    root = HERE / "proposals"
    index = json.loads((root / "semantic-index.json").read_text())
    if index.get("assignment_id") != HERE.name or index.get("format") != "worker-semantic-delivery":
        raise ValueError("semantic index identity differs")
    refs = [index["source"]]
    for value in index["stages"].values():
        refs.extend(value if isinstance(value, list) else [value])
    for ref in refs:
        path = REPO / ref["path"] if ref in (index["source"],) else HERE / ref["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("semantic source hash differs: " + ref["path"])
    load = lambda name: json.loads((root / name).read_text())
    request = {"cell": assignment["cell"], "actor": assignment["actor"]}
    common = {"request": request, "law_records": {assignment["law_id"]: assignment["law"]},
              "dependencies": []}
    for name in ("relevance_batch", "relevance"):
        stages.validate(name, load(name + ".json"), common)
    rules = json.loads((REPO / "runtime/scenario_pipeline/data/canonical_parameter_aliases.json").read_text())
    template = load("template.json")
    stages.validate("template", template, {"request": {"law_id": assignment["law_id"],
                                                   "actor": assignment["actor"]},
                                           "law_record": assignment["law"],
                                           "canonical_parameter_rules": rules,
                                           "dependencies": []})
    for index, expected in enumerate(template["structure"]["judgment_calls_needed"], 1):
        observed = load(f"judgment-{index}.json")
        stages.validate("judgment_observables", observed,
                        {"request": {"template_id": template["template_id"],
                                     "phrase": expected["phrase"], "note": expected["note"]},
                         "dependencies": []})
        expected["observable_requirements"] = observed["observable_requirements"]
    binding = load("bindings.json")
    stages.validate("bindings", binding,
                    {"request": dict(request, template_ids=[template["template_id"]]),
                     "canonical_parameter_rules": rules, "dependencies": [template]})
    stages.validate("cases", load("cases.json"),
                    {"request": request, "dependencies": [binding], "templates": [template],
                     "canonical_parameter_rules": rules, "judgment_completion_policy": {}})


if __name__ == "__main__":
    validate()
    print("All source-bound draft semantic stages passed pinned validation")
