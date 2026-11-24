"""Five exact case source joins and missing-source rejection."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
from worker_exchange.measurement_contract import validate, verify_report


class DiagnosticMeasurements(unittest.TestCase):
    def test_five_exact_positive_and_negative(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        manifest = json.loads((ROOT / 'diagnostic-manifest.json').read_text())
        scratch = REPO / '.runtime-work/c111125-tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                construction = json.loads((ROOT / entry['construction']).read_text())
                files = {f['path']: f['content'] for f in construction['files']}
                contract = json.loads((ROOT / entry['measurement_contract']).read_text())
                validate(contract, plan['requirement_dispositions'], files['analysis.py'], entry['case_id'])
                with tempfile.TemporaryDirectory(dir=scratch) as directory:
                    base = Path(directory)
                    positive = base / 'positive'
                    materialize(REPO, REPO / entry['fixture_recipe'], positive)
                    (positive / 'config.json').write_text(files['config.json'])
                    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
                    command = [sys.executable, str(ROOT / 'analysis.py'), '--attempt',
                               str(positive), '--output', str(positive / 'analysis-report.json')]
                    result = subprocess.run(command, capture_output=True, text=True, env=env)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    report = json.loads((positive / 'analysis-report.json').read_text())
                    self.assertFalse(report['physical_acceptance_claimed'])
                    self.assertFalse(report['legal_verdict_claimed'])
                    self.assertEqual(len(verify_report(contract, report, positive)), 2)
                    negative = base / 'negative'
                    materialize(REPO, REPO / entry['fixture_recipe'], negative)
                    (negative / 'config.json').write_text(files['config.json'])
                    (negative / contract['negative']['remove'][0]).unlink()
                    command[command.index(str(positive))] = str(negative)
                    command[-1] = str(negative / 'analysis-report.json')
                    result = subprocess.run(command, capture_output=True, text=True, env=env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(contract['negative']['error_contains'], result.stderr)


if __name__ == '__main__':
    unittest.main()
