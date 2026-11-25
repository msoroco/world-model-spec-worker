"""Pinned runtime schema validation for four source-gated measurements."""
import json
import unittest
from pathlib import Path

from worker_exchange.measurement_contract import validate
from reviewed_scene import ASSIGNMENT, VARIANTS


class SelectedMeasurementContractTests(unittest.TestCase):
    def test_four_exact_selected_contracts(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / "case-plan.json").read_text())
        code = (root / "analysis.py").read_text()
        for index, suffix in enumerate(VARIANTS):
            case_id = ASSIGNMENT + "__" + suffix
            contract = root / ("measurement-contract.json" if index == 0 else
                               f"cases/{suffix}/measurement-contract.json")
            data = json.loads(contract.read_text())
            rows = validate(data, plan["requirement_dispositions"], code, case_id)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["inputs"], ["trace.json", "relation.json"])


if __name__ == "__main__":
    unittest.main()
