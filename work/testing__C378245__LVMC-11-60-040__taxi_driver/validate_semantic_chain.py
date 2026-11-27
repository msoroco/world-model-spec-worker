"""Validate exact taxi semantic stages against frozen assignment and runtime."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work"
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output_root or SCRATCH.resolve() not in Path(output_root).resolve().parents:
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from batch_pipeline import stages  # noqa: E402


def load(name: str) -> dict:
    return json.loads((ROOT / "proposals" / name).read_text())


def check() -> None:
    original = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    index = load("semantic-index.json")
    if index["assignment_id"] != original["assignment_id"]:
        raise ValueError("semantic index assignment differs")
    for stage, refs in index["stages"].items():
        for ref in refs if isinstance(refs, list) else [refs]:
            path = REPO / "work" / ROOT.name / ref["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError("semantic stage source hash differs: " + stage)
    request = {"cell": original["cell"], "actor": original["actor"]}
    common = {"request": request, "law_records": {original["law_id"]: original["law"]},
              "dependencies": []}
    for stage in ("relevance_batch", "relevance"):
        stages.validate(stage, load(stage + ".json"), deepcopy(common))
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    template = load("template.json")
    stages.validate("template", template,
                    {"request": {"law_id": original["law_id"], "actor": original["actor"]},
                     "law_record": original["law"], "canonical_parameter_rules": rules,
                     "dependencies": []})
    observed = load("judgment-expeditiousness.json")
    stages.validate("judgment_observables", observed,
                    {"request": {"template_id": template["template_id"],
                                 "phrase": observed["phrase"], "note": observed["note"]},
                     "dependencies": []})
    template["structure"]["judgment_calls_needed"][0]["observable_requirements"] = observed["observable_requirements"]
    bindings = load("bindings.json")
    stages.validate("bindings", bindings,
                    {"request": dict(request, template_ids=[template["template_id"]]),
                     "canonical_parameter_rules": rules, "dependencies": [template]})
    stages.validate("cases", load("cases.json"),
                    {"request": request, "dependencies": [bindings], "templates": [template],
                     "canonical_parameter_rules": rules, "judgment_completion_policy": {}})
    print(json.dumps({"assignment_id": original["assignment_id"],
                      "validated_stages": ["relevance_batch", "relevance", "template",
                                           "judgment_observables", "bindings", "cases"],
                      "judgment_sweep_status": "incomplete, explicitly source-gated",
                      "simulation_started": False}))


if __name__ == "__main__":
    check()
