"""Validate five exact selected measurement contracts with the pinned runtime."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if output != ROOT / ".runtime-work" and ROOT / ".runtime-work" not in output.parents:
        raise ValueError("runtime pipeline output root must be under .runtime-work")
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from worker_exchange.measurement_contract import validate
    plan = json.loads((HERE / "case-plan.json").read_text())
    analysis = (HERE / "analysis.py").read_text()
    for case in plan["cases"]:
        path = HERE / "cases" / case["case_suffix"] / "measurement-contract.json"
        contract = json.loads(path.read_text())
        rows = validate(contract, plan["requirement_dispositions"],
                        analysis, case["case_id"])
        print(case["case_suffix"], len(rows))


if __name__ == "__main__":
    main()
