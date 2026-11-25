"""Validate exact draft semantic stages and four selected measurement contracts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))

from worker_exchange.semantic_delivery import validate as validate_semantic
from worker_exchange.measurement_contract import validate as validate_measurement


def main() -> None:
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
    print(validate_semantic(HERE, assignment, manifest))
    plan = json.loads((HERE / "case-plan.json").read_text())
    code = (HERE / "analysis.py").read_text()
    for case in plan["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[1]
        contract = json.loads((HERE / "cases" / suffix / "measurement-contract.json").read_text())
        rows = validate_measurement(contract, plan["requirement_dispositions"], code,
                                    case["case_id"])
        print(suffix, len(rows))


if __name__ == "__main__":
    main()
