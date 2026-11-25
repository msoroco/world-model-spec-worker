"""Exact selected witness maps to one source-bound analyzer output."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from scenario_pipeline.worker_exchange import measurement_contract

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import analyze
from test_saved_backing import fixture


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

    def test_source_hashed_report_matches_selected_contract(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as temp:
            attempt = Path(temp)
            fixture(attempt)
            (attempt / 'config.json').write_text((ROOT / 'config.json').read_text())
            report = analyze(attempt)
            contract = json.loads((ROOT / 'measurement-pedestrian_yield.json').read_text())
            values = measurement_contract.verify_report(contract, report, attempt)
            self.assertEqual(set(values), {'pedestrian_precedence'})
            (attempt / 'map.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                measurement_contract.verify_report(contract, report, attempt)


if __name__ == '__main__':
    unittest.main()
