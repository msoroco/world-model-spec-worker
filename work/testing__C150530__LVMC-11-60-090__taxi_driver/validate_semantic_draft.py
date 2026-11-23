"""Validate authored semantic stages against pinned CPU stage contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not OUTPUT or not Path(OUTPUT).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from batch_pipeline import stages  # noqa: E402

ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"
FOLDER = ROOT / "work" / ASSIGNMENT / "proposals"


def load(stage: str) -> dict:
    return json.loads((FOLDER / (stage + ".json")).read_text())


def validate() -> None:
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    request = {"cell": assignment["cell"], "actor": assignment["actor"]}
    common = {"request": request,
              "law_records": {assignment["law_id"]: assignment["law"]},
              "dependencies": []}
    for stage in ("relevance_batch", "relevance"):
        stages.validate(stage, load(stage), common)
    rules = json.loads((ROOT / "runtime" / "scenario_pipeline" / "data" /
                        "canonical_parameter_aliases.json").read_text())
    template = load("template")
    stages.validate("template", template,
                    {"request": {"law_id": assignment["law_id"],
                                 "actor": assignment["actor"]},
                     "law_record": assignment["law"],
                     "canonical_parameter_rules": rules, "dependencies": []})
    stages.validate("bindings", load("bindings"),
                    {"request": dict(request, template_ids=[template["template_id"]]),
                     "canonical_parameter_rules": rules,
                     "dependencies": [template]})
    stages.validate("cases", load("cases"),
                    {"request": request, "dependencies": [load("bindings")],
                     "templates": [template], "canonical_parameter_rules": rules,
                     "judgment_completion_policy": {}})
    print("five semantic stage drafts validated; hashed semantic index pending")


if __name__ == "__main__":
    validate()
