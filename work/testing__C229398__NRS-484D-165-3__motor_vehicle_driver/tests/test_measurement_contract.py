import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / "runtime" / "scenario_pipeline"))
from worker_exchange.measurement_contract import validate


class MeasurementContractTest(unittest.TestCase):
    def test_all_exact_case_requirements_bind_finalizer_methods(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        code = (ROOT / "finalize_original.py").read_text()
        self.assertEqual(len(plan["requirement_dispositions"]), 5)
        for case in plan["cases"]:
            key = case["case_key"]
            contract = json.loads((ROOT / "cases" / key / "measurement-contract.json").read_text())
            rows = validate(contract, plan["requirement_dispositions"], code, case["case_id"])
            self.assertEqual(len(rows), 5)


if __name__ == "__main__":
    unittest.main()
