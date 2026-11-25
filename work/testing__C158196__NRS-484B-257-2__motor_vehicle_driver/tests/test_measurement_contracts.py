import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
if ".runtime-work" not in Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).parts:
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.measurement_contract import validate


class ContractTest(unittest.TestCase):
    def test_each_exact_case_maps_its_selected_law_requirements(self):
        plan = json.loads((FOLDER / "case-plan.json").read_text())
        analysis = (FOLDER / "analysis.py").read_text()
        for case in plan["cases"]:
            suffix = case["case_id"].split("__")[-1]
            contract = json.loads((FOLDER / ("measurement-" + suffix + ".json")).read_text())
            self.assertTrue(validate(contract, plan["requirement_dispositions"],
                                     analysis, case["case_id"]))


if __name__ == "__main__":
    unittest.main()
