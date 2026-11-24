"""CPU-test prospective Native comparison audit on synthetic source fixtures."""

import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
from native_comparison_audit import prove  # noqa: E402
from prove_delivery_acceptance import source_for  # noqa: E402


scratch = Path(output) / "native-comparison-indexes"
scratch.mkdir(parents=True, exist_ok=True)
cases = json.loads((HERE / "case-plan.json").read_text())["comparisons"]
for comparison in cases:
    name = comparison["comparison_id"]
    index = {"attempts": {case_id: str(source_for(case_id.split("__")[-1]))
                          for case_id in comparison["case_ids"]}}
    path = scratch / (name + ".json")
    path.write_text(json.dumps(index) + "\n")
    positive = prove(name, path, diagnostic=True)
    if positive["passed"] is not False or positive["diagnostic_fixture"] is not True:
        raise AssertionError("CPU fixture was accepted as Native")
    missing = {"attempts": dict(index["attempts"])}
    missing["attempts"].pop(comparison["case_ids"][-1])
    missing_path = scratch / (name + "-missing.json")
    missing_path.write_text(json.dumps(missing) + "\n")
    try:
        prove(name, missing_path, diagnostic=True)
    except ValueError as error:
        if "Comparison index omits or adds an exact case" not in str(error):
            raise
    else:
        raise AssertionError("Comparison accepted a missing exact case")
    try:
        prove(name, path, diagnostic=False)
    except ValueError as error:
        if "Native source provenance required" not in str(error):
            raise
    else:
        raise AssertionError("Comparison accepted synthetic source as Native")
    print(json.dumps({"comparison_id": name, "case_ids": comparison["case_ids"],
                      "diagnostic_positive": True,
                      "missing_case_rejected": True,
                      "synthetic_native_rejected": True,
                      "native_or_legal_acceptance_claimed": False}))
print("PASS all six prospective Native comparison CPU tests")
