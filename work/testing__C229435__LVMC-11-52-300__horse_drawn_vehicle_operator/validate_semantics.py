"""Validate every draft canonical stage against the pinned CPU runtime."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def main():
    out = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not out or not Path(out).resolve().is_relative_to((ROOT / ".runtime-work").resolve()):
        raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports")
    sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
    from batch_pipeline import stages
    from worker_exchange.measurement_contract import validate as validate_measurement
    assignment = read(ROOT / "inputs" / PACKAGE.name / "assignment.json")
    plan = read(PACKAGE / "case-plan.json")
    relevance = read(PACKAGE / "proposals/relevance.json")
    template = read(PACKAGE / "proposals/template.json")
    bindings = read(PACKAGE / "proposals/bindings.json")
    cases = read(PACKAGE / "proposals/cases.json")
    rules = read(stages.ROOT / "data/canonical_parameter_aliases.json")
    request = {"cell": assignment["cell"], "actor": assignment["actor"]}
    for stage in ("relevance_batch", "relevance"):
        stages.validate(stage, relevance, {"request": request, "law_records": {assignment["law_id"]: assignment["law"]}, "dependencies": []})
    stages.validate("template", template, {"request": {"law_id": assignment["law_id"], "actor": assignment["actor"]}, "law_record": assignment["law"], "canonical_parameter_rules": rules, "dependencies": []})
    stages.validate("bindings", bindings, {"request": dict(request, template_ids=[template["template_id"]]), "canonical_parameter_rules": rules, "dependencies": [template]})
    stages.validate("cases", cases, {"request": request, "dependencies": [bindings], "templates": [template], "canonical_parameter_rules": rules, "judgment_completion_policy": {}})
    planned = {case["case_id"] for case in plan["cases"]}
    selected = {case["case_id"] for case in cases["cases"] if case["target_type"] != "baseline"}
    if planned != selected:
        raise ValueError("canonical cases differ from exact plan")
    code = (PACKAGE / "analysis.py").read_text()
    for case_id in sorted(selected):
        suffix = case_id.rsplit("__", 1)[1]
        contract = read(PACKAGE / "cases" / suffix / "measurement-contract.json")
        validate_measurement(contract, plan["requirement_dispositions"], code, case_id)
    print(f"Validated relevance, template, bindings, {len(selected)} selected cases and {len(selected)} exact measurement contracts")


if __name__ == "__main__":
    main()
