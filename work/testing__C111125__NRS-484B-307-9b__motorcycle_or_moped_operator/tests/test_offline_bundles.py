import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OfflineBundles(unittest.TestCase):
    def test_all_six_exact_sources_and_case_parameters(self):
        plan_source = (ROOT / 'case-plan.json').read_bytes()
        plan = json.loads(plan_source)
        manifest = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
        by_id = {row['case_id']: row for row in plan['cases']}
        self.assertEqual(len(by_id), 6)
        self.assertEqual({row['case_id'] for row in manifest['cases']}, set(by_id))
        for item in manifest['cases']:
            path = ROOT / item['construction']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             item['construction_sha256'])
            construction = json.loads(path.read_text())
            self.assertTrue(construction['diagnostic_only'])
            files = {row['path']: row['content'] for row in construction['files']}
            config = json.loads(files['config.json'])
            self.assertEqual(config['selected_case_id'], item['case_id'])
            self.assertEqual(config['case_parameters'],
                             by_id[item['case_id']]['scenario_parameters'])
            self.assertEqual(config['plan_sha256'], hashlib.sha256(plan_source).hexdigest())
            self.assertEqual((config['fps'], config['frame_count'], config['duration_s']),
                             (20, 900, 45))
            self.assertEqual(config['cameras'],
                             ['overview', 'approach', 'reference_corner', 'driver_reference'])
            for name in ('signal_exception.py', 'original_capture.py',
                         'saved_measurement.py', 'comparison_audit.py',
                         'delivery_audit.py', 'media_decode.py'):
                self.assertEqual(files[name], (ROOT / name).read_text())


if __name__ == '__main__':
    unittest.main()
