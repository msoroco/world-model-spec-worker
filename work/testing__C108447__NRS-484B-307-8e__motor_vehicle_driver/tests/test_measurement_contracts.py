"""Source-shaped exact-case measurement and missing-source proofs."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime'))
from analysis import build_report
from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report


class MeasurementContractTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work' / 'p02-c108447-2'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = json.loads((HERE / 'case-plan.json').read_text())
        self.manifest = json.loads((HERE / 'execution-manifest.draft.json').read_text())

    def fixture(self, suffix):
        root = self.root / suffix
        root.mkdir()
        spec = json.loads((HERE / 'diagnostics' / suffix / 'specification.json').read_text())
        for name, content in spec['files'].items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        construction = json.loads((HERE / 'constructions' / (suffix + '.json')).read_text())
        config = next(row['content'] for row in construction['files'] if row['path'] == 'config.json')
        (root / 'config.json').write_text(config)
        return root

    def test_all_six_selected_measurements_and_exact_sources(self):
        for entry in self.manifest['cases']:
            suffix = entry['case_id'].rsplit('__', 1)[1]
            with self.subTest(suffix=suffix):
                root = self.fixture(suffix)
                construction = json.loads((HERE / entry['construction']).read_text())
                code = next(row['content'] for row in construction['files'] if row['path'] == 'analysis.py')
                contract = json.loads((HERE / entry['measurement_contract']).read_text())
                validate(contract, self.plan['requirement_dispositions'], code, entry['case_id'])
                report = build_report(root)
                self.assertEqual(report['case_id'], entry['case_id'])
                self.assertTrue(report['diagnostic_fixture'])
                self.assertFalse(report['legal_verdict_claimed'])
                self.assertEqual(len(verify_report(contract, report, root)), 5)

    def test_missing_and_mutated_authority_rejected(self):
        root = self.fixture('private_bypass')
        (root / 'authority.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source: authority.json'):
            build_report(root)
        (root / 'authority.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Original property/map source seal differs'):
            build_report(root)

    def test_foreign_case_rejected(self):
        root = self.fixture('private_bypass')
        config = json.loads((root / 'config.json').read_text())
        config['selected_case_id'] = 'foreign__case'
        (root / 'config.json').write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'Foreign exact property case'):
            build_report(root)


if __name__ == '__main__':
    unittest.main()
