"""Bind the authored view coverage to the executable Native camera calls."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c132497_capture_camera',
    ROOT/'native/capture.py')
CAPTURE = importlib.util.module_from_spec(SPEC)
import sys
sys.path.insert(0, str(ROOT/'native'))
SPEC.loader.exec_module(CAPTURE)


class CameraCoveragePlan(unittest.TestCase):
    def test_views_dimensions_and_duration_match_capture(self):
        plan = json.loads((ROOT/'case-plan.json').read_text())['camera_plan']
        config = json.loads((ROOT/'config.json').read_text())
        self.assertEqual(plan['duration_s'], config['frames']/config['rate_hz'])
        self.assertEqual(plan['composition'], 'synchronized_four_view_primary')
        expected = {item['name']:(item['width'],item['height'],item['fov_deg'])
                    for item in config['cameras']}
        self.assertEqual({row['view'] for row in plan['coverage']}, set(expected))
        for policy in ('standard','elevated_overview'):
            actual = {name:(width,height,fov)
                      for name,width,height,fov,*_ in CAPTURE.camera_plan(policy)}
            self.assertEqual(actual, expected)
        self.assertNotEqual(CAPTURE.camera_plan('standard')[0][4],
                            CAPTURE.camera_plan('elevated_overview')[0][4])
        self.assertTrue(plan['physical_visibility_unverified'])


if __name__ == '__main__': unittest.main()
