"""Exact case source joins and missing-source rejection."""
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
from worker_exchange.native_output import validate_result


class DiagnosticMeasurements(unittest.TestCase):
    def test_exact_positive_and_negative(self):
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
                    self.assertEqual(len(verify_report(contract, report, positive)),
                                     len(contract['requirements']))
                    self.assertIsNone(report['device_timeline']['legal_verdict'])
                    execution = validate_result(json.loads((positive / 'result.json').read_text()))
                    self.assertEqual(execution['case_id'], entry['case_id'])
                    self.assertEqual(execution['recording_description'], construction['recording_description'])
                    self.assertFalse(execution['setup_confirmed'])
                    self.assertFalse(execution['target_checks'][0]['physical_cause_confirmed'])
                    self.assertEqual(len((positive / execution['recording_evidence'][0]['reference']).read_text().splitlines()),
                                     len(json.loads((positive / 'frames.json').read_text())))
                    self.assertTrue((positive / execution['recording_evidence'][1]['reference']).is_file())
                    negative = base / 'negative'
                    materialize(REPO, REPO / entry['fixture_recipe'], negative)
                    (negative / 'config.json').write_text(files['config.json'])
                    (negative / contract['negative']['remove'][0]).unlink()
                    command[command.index(str(positive))] = str(negative)
                    command[-1] = str(negative / 'analysis-report.json')
                    result = subprocess.run(command, capture_output=True, text=True, env=env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(contract['negative']['error_contains'], result.stderr)
                    self.assertFalse((negative / 'result.json').exists())
                    mismatch = base / 'mismatch'
                    materialize(REPO, REPO / entry['fixture_recipe'], mismatch)
                    (mismatch / 'config.json').write_text(files['config.json'])
                    trace_path = mismatch / 'trace.jsonl'
                    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
                    rows[1]['position']['x'] += 1
                    trace_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                    command[command.index(str(negative))] = str(mismatch)
                    command[-1] = str(mismatch / 'analysis-report.json')
                    result = subprocess.run(command, capture_output=True, text=True, env=env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('Diagnostic frame, trace and video map disagree', result.stderr)
                    self.assertFalse((mismatch / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
