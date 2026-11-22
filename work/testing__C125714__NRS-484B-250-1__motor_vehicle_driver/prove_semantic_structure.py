"""Check draft case structure without asserting that site law guards are met.

The shadow binding exists only in memory. It proves that the authored case
records satisfy the pinned stage schema if source review later permits an
active binding. It is never returned as an adopted or ready proposal.
"""
import json
import os
from pathlib import Path

from batch_pipeline import stages
from scenario_pipeline.worker_exchange.semantic_delivery import validate as validate_delivery


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(name):
    return json.loads((ROOT / "proposals" / name).read_text())


def main():
    output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if output != (REPO / ".runtime-work").resolve() and (REPO / ".runtime-work").resolve() not in output.parents:
        raise ValueError("Runtime output root must stay under .runtime-work")
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    manifest = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
    try:
        validate_delivery(ROOT, assignment, manifest)
    except ValueError as exc:
        if str(exc) != "Assigned law must be an active binding":
            raise
        actual = str(exc)
    else:
        raise AssertionError("Conditional binding unexpectedly passed delivery validation")

    binding, cases, template = (read(name) for name in ("bindings.json", "cases.json", "template.json"))
    binding["law_refs"] = [{"template_id": template["template_id"], "binding_kind": "direct"}]
    binding["context_refs"] = []
    binding["variable_parameters"] = [
        {"name": name, "kind": assignment["kind"], "used_by_laws": [template["template_id"]]}
        for name, assignment in cases["cases"][0]["variable_assignments"].items()
    ]
    request = {"cell": {"cell_id": assignment["cell_id"]}, "actor": assignment["actor"],
               "template_ids": [template["template_id"]]}
    rules = json.loads((REPO / "runtime" / "scenario_pipeline" / "data" /
                        "canonical_parameter_aliases.json").read_text())
    stages.validate("bindings", binding, {"request": request,
                    "canonical_parameter_rules": rules, "dependencies": [template]})
    for index in (1, 2):
        observed = read(f"judgment-{index}.json")
        template["structure"]["judgment_calls_needed"][index - 1]["observable_requirements"] = observed["observable_requirements"]
    stages.validate("cases", cases, {"request": request, "dependencies": [binding],
                    "templates": [template], "canonical_parameter_rules": rules,
                    "judgment_completion_policy": {}})
    print(json.dumps({"actual_delivery_validation": actual,
                      "shadow_active_schema": "passed_in_memory_only",
                      "draft_case_count": len(cases["cases"]),
                      "selected_case_count": len(manifest["cases"]),
                      "source_guards_accepted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
