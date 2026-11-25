"""Exact selected witness maps to one source-bound analyzer output."""
import json
from pathlib import Path
import unittest

from scenario_pipeline.worker_exchange import measurement_contract

ROOT = Path(__file__).resolve().parents[1]


class MeasurementContractTests(unittest.TestCase):
    def test_both_exact_contracts_validate(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        code = (ROOT / 'analysis.py').read_text()
        for suffix in ('pedestrian_yield', 'pedestrian_continue'):
            contract = json.loads((ROOT / ('measurement-' + suffix + '.json')).read_text())
            rows = measurement_contract.validate(
                contract, plan['requirement_dispositions'], code,
                ROOT.name + '__' + suffix)
            self.assertEqual(len(rows), 1)


if __name__ == '__main__':
    unittest.main()
