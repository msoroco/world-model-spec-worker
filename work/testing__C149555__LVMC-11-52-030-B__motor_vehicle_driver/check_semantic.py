"""Validate authored canonical stage proposals against the pinned contracts."""

import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
    raise ValueError("Route runtime imports to .runtime-work first")
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from batch_pipeline import stages


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


assignment = read(ROOT / "inputs" / FOLDER.name / "assignment.json")
index = read(FOLDER / "proposals" / "semantic-index.json")
if index.get("assignment_id") != assignment["assignment_id"]:
    raise ValueError("Semantic index assignment mismatch")
for name, references in index["stages"].items():
    for reference in references if isinstance(references, list) else [references]:
        path = FOLDER / reference["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != reference["sha256"]:
            raise ValueError("Semantic stage source hash changed: " + name)
proposal = lambda name: read(FOLDER / "proposals" / (name + ".json"))
common = {"request": {"cell": assignment["cell"], "actor": assignment["actor"]},
          "law_records": {assignment["law_id"]: assignment["law"]}, "dependencies": []}
for stage in ("relevance_batch", "relevance"):
    stages.validate(stage, proposal("relevance"), common)
rules = read(stages.ROOT / "data" / "canonical_parameter_aliases.json")
template = proposal("template")
stages.validate("template", template, {"request": {"law_id": assignment["law_id"],
                                                 "actor": assignment["actor"]},
                                       "law_record": assignment["law"],
                                       "canonical_parameter_rules": rules, "dependencies": []})
binding = proposal("bindings")
stages.validate("bindings", binding, {"request": {"cell": assignment["cell"],
                                                  "actor": assignment["actor"],
                                                  "template_ids": [template["template_id"]]},
                                        "canonical_parameter_rules": rules,
                                        "dependencies": [template]})
stages.validate("cases", proposal("cases"), {"request": {"cell": assignment["cell"],
                                                        "actor": assignment["actor"]},
                                               "dependencies": [binding], "templates": [template],
                                               "canonical_parameter_rules": rules,
                                               "judgment_completion_policy": {}})
print("six exact cases and all authored semantic stage contracts passed")
