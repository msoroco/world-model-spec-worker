"""Exact selected witness requirements bind to executable saved methods."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.measurement_contract import validate


class MeasurementContracts(unittest.TestCase):
    def test_all_selected_case_contracts(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        source = (ROOT / 'analysis.py').read_text()
        for case in plan['cases']:
            suffix = case['case_id'].removeprefix(ROOT.name + '__')
            path = ROOT / 'cases' / suffix / 'measurement-contract.json'
            with self.subTest(suffix=suffix):
                contract = json.loads(path.read_text())
                self.assertEqual(contract['case_id'], case['case_id'])
                validate(contract, plan['requirement_dispositions'], source, case['case_id'])


if __name__ == '__main__':
    unittest.main()
