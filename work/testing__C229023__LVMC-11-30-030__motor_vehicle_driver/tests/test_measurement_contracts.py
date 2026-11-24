import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_measurement_contracts import build

output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not output or not Path(output).resolve().is_relative_to((HERE.parents[1] / ".runtime-work").resolve()):
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before pinned contract import")
sys.path.insert(0, str(HERE.parents[1] / "runtime"))
from scenario_pipeline.worker_exchange import measurement_contract


class MeasurementContractTests(unittest.TestCase):
    def test_six_exact_source_bound_contracts(self):
        paths = build()
        self.assertEqual(len(paths), 6)
        for path in paths:
            contract = json.loads(path.read_text())
            self.assertEqual(contract["status"], "draft_unselected")
            self.assertEqual(contract["case_id"].split("__")[-1], path.parent.name)
            self.assertEqual(contract["requirements"][0]["disposition_index"], 0)
            self.assertIn("trace.jsonl", contract["requirements"][0]["inputs"])
            self.assertEqual(contract["negative"]["remove"], ["context.json"])
            disposition = {"status": "selected_required", "case_ids": [contract["case_id"]],
                           "requirement": contract["requirements"][0]["requirement"],
                           "source": contract["requirements"][0]["source"]}
            rows = measurement_contract.validate(contract, [disposition],
                                                 (HERE / "analysis.py").read_text(),
                                                 contract["case_id"])
            self.assertEqual(rows[0]["output_key"], "crosswalk_observation")


if __name__ == "__main__":
    unittest.main()
