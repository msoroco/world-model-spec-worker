"""Rebound construction tests use fake Native map and source packets only."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rebind_reviewed_execution import rebind
from test_bind_reviewed_site import pair


class ReboundExecutionTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / '.runtime-work' / 'c150041-rebind-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_six_cases_two_candidates_rebind_packet_and_scene(self):
        packets = pair(self.root)
        destination = self.root / 'rebound'
        manifest_path = rebind(packets['park'], packets['stand'], destination)
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(len(manifest['cases']), 6)
        self.assertEqual(manifest['preparation_status'],
                         'review_and_cpu_proofs_pending')
        for case in manifest['cases']:
            activity = case['activity']
            for variant in case['variants']:
                bundle = json.loads((destination / variant['construction']).read_text())
                files = {row['path']: row['content'] for row in bundle['files']}
                scene = json.loads(files['scene.json'])
                config = json.loads(files['config.json'])
                self.assertEqual(scene['source_packet_sha256'],
                                 manifest['packet_sha256'][activity])
                self.assertEqual(config['reviewed_source_packet']['sha256'],
                                 scene['source_packet_sha256'])
                self.assertEqual(config['selected_case_id'], case['case_id'])
                self.assertIn('reviewed_sources/native-map.xodr', files)
                self.assertIn('reviewed-context.json', files)
                self.assertIn('check_materialized_package',
                              files['tests/test_delivery_offline.py'])
                self.assertFalse(scene['physical_realization_claimed'])
        with self.assertRaisesRegex(ValueError, 'fresh rebind output'):
            rebind(packets['park'], packets['stand'], destination)
        for case in manifest['cases']:
            for variant in case['variants']:
                with self.subTest(case=case['case_id'], candidate=variant['id']):
                    offline = self.root / 'offline' / case['case_id'] / variant['id']
                    run = subprocess.run(
                        [sys.executable, str(ROOT.parents[1] / 'runtime.py'), 'offline',
                         '--manifest', str(destination / 'execution-manifest.json'),
                         '--case', case['case_id'], '--candidate', variant['id'],
                         '--output', str(offline)],
                        cwd=ROOT.parents[1], capture_output=True, text=True,
                        timeout=120)
                    detail = ((offline / 'offline.log').read_text()
                              if (offline / 'offline.log').is_file() else '')
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr + detail)
                    receipt = json.loads(run.stdout)
                    self.assertTrue(receipt['offline_passed'])
                    self.assertFalse(receipt['simulation_started'])

    def test_changed_retained_source_does_not_publish(self):
        packets = pair(self.root)
        (packets['stand'].parent / 'reviewed_sources/activity.txt').write_text('changed\n')
        destination = self.root / 'invalid'
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            rebind(packets['park'], packets['stand'], destination)
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
