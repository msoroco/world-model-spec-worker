"""Check exact root dispatch and source-limited camera plan."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bus363_dispatch', ROOT / 'runner.py')
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


class PackageTest(unittest.TestCase):
    def test_exact_case_coverage(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        for case in manifest['cases']:
            self.assertEqual(dispatch.check(case['case_id'])['case_id'], case['case_id'])
        with self.assertRaisesRegex(ValueError, 'exact prepared'):
            dispatch.check('different assignment')

    def test_four_view_source_plan(self):
        config = json.loads((ROOT / 'config.json').read_text())
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        self.assertEqual(config['duration_s'], 30)
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual([camera['name'] for camera in config['cameras']],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertEqual({item['view'] for item in plan['camera_plan']['coverage']},
                         {camera['name'] for camera in config['cameras']})
        self.assertEqual({item['name'] for item in plan['observations']},
                         {'school_crossing_observation'})


if __name__ == '__main__':
    unittest.main()
