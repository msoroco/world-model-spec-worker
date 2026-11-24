"""Every exact selected timing case has the same source-backed contract."""
import json
import hashlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',str(REPO/'.runtime-work'/'c125751-contract-tests'))
sys.path.insert(0,str(REPO/'runtime'))
from scenario_pipeline.worker_exchange.measurement_contract import validate


class MeasurementContractTests(unittest.TestCase):
    def test_selected_manifest_binds_all_exact_cases_without_false_readiness(self):
        manifest = json.loads((ROOT/'execution-manifest.json').read_text())
        self.assertEqual(manifest['status'],'partial_selected_delivery')
        self.assertEqual(len(manifest['cases']),5)
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                self.assertEqual(entry['kind'],'delivery')
                self.assertEqual(hashlib.sha256((ROOT/entry['construction']).read_bytes()).hexdigest(),
                                 entry['construction_sha256'])
                self.assertEqual(hashlib.sha256((ROOT/entry['offline']['log']).read_bytes()).hexdigest(),
                                 entry['offline']['log_sha256'])
                self.assertEqual(entry['offline']['exit_code'],0)
                self.assertTrue(entry['missing_proofs'])

    def test_all_exact_cases_have_valid_selected_requirements(self):
        plan = json.loads((ROOT/'case-plan.json').read_text())
        analysis = (ROOT/'analysis.py').read_text()
        for case in plan['cases']:
            suffix = case['case_id'].removeprefix(ROOT.name+'__')
            contract = json.loads((ROOT/('measurement-contract-'+suffix+'.json')).read_text())
            with self.subTest(case=suffix):
                self.assertEqual(contract['case_id'],case['case_id'])
                rows = validate(contract,plan['requirement_dispositions'],analysis,case['case_id'])
                self.assertEqual(len(rows),4)
                self.assertEqual({row['kind'] for row in rows},{'measured','sourced_context'})

    def test_missing_crossing_source_is_not_a_valid_contract(self):
        plan = json.loads((ROOT/'case-plan.json').read_text())
        case = plan['cases'][0]['case_id']
        contract = json.loads((ROOT/'measurement-contract-precedence.json').read_text())
        contract['negative']['remove'] = ['trace.jsonl']
        with self.assertRaisesRegex(ValueError,'case-specific required input'):
            validate(contract,plan['requirement_dispositions'],(ROOT/'analysis.py').read_text(),case)


if __name__ == '__main__':
    unittest.main()
