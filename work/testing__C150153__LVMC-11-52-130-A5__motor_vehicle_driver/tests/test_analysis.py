"""Selected saved analyzer and exact witness contract diagnostic protocol tests."""
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'runtime/scenario_pipeline'))
from analysis import run
from test_independent_delivery_audit import DeliveryAuditTests
from test_reviewed_site import ReviewedSiteTests
from worker_exchange.measurement_contract import validate, verify_report


class SelectedAnalysisTests(unittest.TestCase):
    def test_positive_and_missing_reviewed_source(self):
        scratch = Path('.runtime-work/c150153-analysis-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, packet, sources, _ = DeliveryAuditTests().fixture(temp)
            selected = attempt / 'reviewed-site'
            selected.mkdir()
            shutil.copy2(packet, selected / 'packet.json')
            shutil.copytree(sources, selected / 'sources')
            plan = json.loads((HERE / 'case-plan.json').read_text())
            case = next(c for c in plan['cases'] if c['case_id'].endswith('__west_inside'))
            config = {'law_id': 'LVMC-11-52-130-A5', 'cell_id': 'C150153',
                      'actor': 'motor_vehicle_driver', 'selected_case_id': case['case_id'],
                      'rate_hz': 20, 'duration_s': 45,
                      'recording_description': case['recording_description']}
            (attempt / 'config.json').write_text(json.dumps(config) + '\n')
            (attempt / 'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
            report = run(attempt, attempt / 'analysis-report.json')
            contract = json.loads((HERE / 'cases/west_inside/measurement-contract.json').read_text())
            validate(contract, plan['requirement_dispositions'], (HERE / 'analysis.py').read_text(), case['case_id'])
            self.assertIn('observed_elevator_requirement', verify_report(contract, report, attempt))
            self.assertEqual(report['case_id'], case['case_id'])
            self.assertEqual(report['measurements']['observed_elevator_requirement']['value']['physical_maneuver_status'], 'not_met')
            result = json.loads((attempt / 'result.json').read_text())
            self.assertFalse(result['maneuver_completed'])
            self.assertEqual(len(result['recording_evidence']), 7)
            required = selected / 'packet.json'
            required.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: reviewed-site/packet.json'):
                run(attempt, attempt / 'negative-report.json')

    def test_all_exact_measurement_contracts_are_selected(self):
        plan = json.loads((HERE / 'case-plan.json').read_text())
        code = (HERE / 'analysis.py').read_text()
        for case in plan['cases']:
            kind = case['case_id'].removeprefix(HERE.name + '__')
            contract = json.loads((HERE / 'cases' / kind / 'measurement-contract.json').read_text())
            with self.subTest(kind=kind):
                validate(contract, plan['requirement_dispositions'], code, case['case_id'])

    def test_all_exact_cases_reject_static_placement(self):
        scratch = Path('.runtime-work/c150153-analysis-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        plan = json.loads((HERE / 'case-plan.json').read_text())
        for case in plan['cases']:
            kind = case['case_id'].removeprefix(HERE.name + '__')
            with self.subTest(kind=kind), TemporaryDirectory(dir=scratch) as temp:
                attempt, packet, sources, _ = DeliveryAuditTests().fixture(temp, case_name=kind)
                selected = attempt / 'reviewed-site'
                selected.mkdir()
                shutil.copy2(packet, selected / 'packet.json')
                shutil.copytree(sources, selected / 'sources')
                (attempt / 'config.json').write_text(json.dumps({
                    'law_id': 'LVMC-11-52-130-A5', 'cell_id': 'C150153',
                    'actor': 'motor_vehicle_driver', 'selected_case_id': case['case_id'],
                    'rate_hz': 20, 'duration_s': 45,
                    'recording_description': case['recording_description']}) + '\n')
                (attempt / 'acquisition-provenance.json').write_text(json.dumps({
                    'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
                run(attempt, attempt / 'analysis-report.json')
                result = json.loads((attempt / 'result.json').read_text())
                self.assertFalse(result['maneuver_completed'])
                self.assertEqual(result['physical_checks']['maneuver']['status'], 'not_met')


if __name__ == '__main__':
    unittest.main()
