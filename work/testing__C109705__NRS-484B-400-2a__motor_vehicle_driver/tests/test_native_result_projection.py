"""Finalizer projects only sealed original fixture sources into Native fields."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]


class NativeResultProjectionTests(unittest.TestCase):
    def test_diagnostic_projection_and_missing_source(self):
        diagnostic = json.loads((BASE / 'cases/near_centerline/diagnostic.json').read_text())
        construction = json.loads((BASE / 'cases/near_centerline/construction.json').read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            attempt = Path(directory)
            for name, content in diagnostic['files'].items():
                target = attempt / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            (attempt / 'construction.json').write_text(json.dumps(construction) + '\n')
            (attempt / 'config.json').write_text(json.dumps(config) + '\n')
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                       PYTHONPATH=str(REPO / 'runtime/scenario_pipeline'),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'c109705-native-result-test-runtime'))
            command = [sys.executable, str(BASE / 'analysis.py'), '--attempt', str(attempt),
                       '--output', str(attempt / 'analysis-report.json')]
            done = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            result = json.loads((attempt / 'result.json').read_text())
            self.assertTrue(result['diagnostic_fixture'])
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertEqual(len(result['recording_evidence']), 4)
            self.assertEqual(len((attempt / 'trace.jsonl').read_text().splitlines()), 900)
            self.assertEqual(result['video_frame_map_reference'], 'video_frames.jsonl')
            (attempt / 'result.json').unlink()
            (attempt / 'analysis-report.json').unlink()
            (attempt / 'intersection-context.json').unlink()
            failed = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('Missing required source: intersection-context.json', failed.stderr)
            self.assertFalse((attempt / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
