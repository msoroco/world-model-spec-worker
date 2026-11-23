"""Check all draft proposals against the pinned semantic stage validators."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""))
if not output_root.is_absolute() or not output_root.is_relative_to(ROOT / ".runtime-work"):
    raise SystemExit("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports")
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from batch_pipeline.stages import validate  # noqa: E402


def read(name):
    return json.loads((HERE / "proposals" / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(bound_cases: Path | None = None):
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    index = read("semantic-index.json")
    assert sha(ROOT / index["source"]["path"]) == index["source"]["sha256"]
    assert sha(HERE / index["case_plan"]["path"]) == index["case_plan"]["sha256"]
    for stage, refs in index["stages"].items():
        for ref in refs if isinstance(refs, list) else [refs]:
            assert sha(HERE / ref["path"]) == ref["sha256"], (stage, ref)
    law = assignment["law"]
    cell = assignment["cell"]
    actor = assignment["actor"]
    law_id = assignment["law_id"]
    rule_path = ROOT / "runtime" / "scenario_pipeline" / "data" / "canonical_parameter_aliases.json"
    rules = json.loads(rule_path.read_text())
    base = {"request": {"cell": cell, "actor": actor}, "law_records": {law_id: law}}
    relevance = read("relevance.json")
    assert relevance == read("relevance_batch.json")
    for stage in ("relevance", "relevance_batch"):
        validate(stage, relevance, base)
    template = read("template.json")
    validate("template", template, {"request": {"law_id": law_id, "actor": actor},
                                    "law_record": law, "canonical_parameter_rules": rules})
    judgment = read("judgment-1.json")
    validate("judgment_observables", judgment,
             {"request": {"template_id": template["template_id"],
                          "phrase": judgment["phrase"], "note": judgment["note"]}})
    template["structure"]["judgment_calls_needed"][0]["observable_requirements"] = judgment["observable_requirements"]
    binding = read("bindings.json")
    validate("bindings", binding,
             {"request": {"cell": cell, "actor": actor, "template_ids": [template["template_id"]]},
              "canonical_parameter_rules": rules})
    cases = read("cases.json")
    validate("cases", cases,
             {"request": {"cell": cell, "actor": actor}, "dependencies": [binding],
              "templates": [template]})
    if bound_cases is not None:
        candidate = json.loads(bound_cases.read_text(encoding="utf-8"))
        validate("cases", candidate,
                 {"request": {"cell": cell, "actor": actor}, "dependencies": [binding],
                  "templates": [template]})
        assert {item["case_id"] for item in candidate["cases"]} == {
            item["case_id"] for item in cases["cases"]}
        assert candidate["frozen_comparisons"] == cases["frozen_comparisons"]
    selected = {item["case_id"] for item in plan["cases"]}
    drafted = {item["case_id"] for item in cases["cases"] if item["target_type"] != "baseline"}
    assert drafted == selected
    assert cases["frozen_comparisons"] == [
        {"comparison_id": item["comparison_id"], "case_ids": item["case_ids"],
         "deliberate_differences": item["deliberate_differences"]}
        for item in plan["comparisons"]]
    assert all(item["variable_assignments"]["ego_speed"]["value"] is None
               for item in cases["cases"])
    print(json.dumps({"stage_validations": 6, "selected_case_ids": len(selected),
                      "frozen_comparisons": len(plan["comparisons"]),
                      "bound_candidate_stage_validated": bound_cases is not None,
                      "status": "draft_numeric_source_and_physical_review_pending"}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bound-cases", type=Path)
    prove(parser.parse_args().bound_cases)
