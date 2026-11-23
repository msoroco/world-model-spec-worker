"""Verify every exact selected requirement against source-shaped CPU fixtures."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXPECTED_OUTPUT = (REPO / ".runtime-work").resolve()
value = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not value or not Path(value).resolve().is_relative_to(EXPECTED_OUTPUT):
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before importing runtime")

sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from worker_exchange.measurement_contract import validate, verify_report
from analysis import build_report
from test_saved_analysis import fixture


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    code = (ROOT / "analysis.py").read_text()
    for kind in ("green_selected_drive", "adjacent_dark_drive",
                 "second_green_drive", "green_selected_stand"):
        case_id = ROOT.name + "__" + kind
        contract = json.loads((ROOT / "cases" / kind / "measurement-contract.json").read_text())
        rows = validate(contract, plan["requirement_dispositions"], code, case_id)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            fixture(source,
                    bus_lane="west" if kind in ("adjacent_dark_drive", "second_green_drive") else "east",
                    green=("east", "west") if kind == "second_green_drive" else ("east",),
                    moving=kind != "green_selected_stand", case_id=kind)
            values = verify_report(contract, build_report(source), source)
            if len(rows) != 3 or len(values) != 3:
                raise ValueError("selected green-arrow requirements not fully measured")
        print(kind, "selected requirements", len(rows), "verified outputs", len(values))


if __name__ == "__main__":
    main()
