"""Materialized 200 m truck sweep bundle check; no simulator is contacted."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
from qualitative_sweep_construction import placement


class BundleTests(unittest.TestCase):
    def test_exact_identity_and_four_source_camera_contract(self):
        config = json.loads(Path(runner.__file__).with_name('config.json').read_text())
        selected = runner.validate_config(config)['selected_case_id']
        self.assertEqual(selected.removeprefix(runner.ASSIGNMENT+'__'), 'conditions_gap_200m')
        self.assertEqual(config['rate_hz'] * config['duration_s'], 900)
        self.assertEqual([item['name'] for item in config['cameras']], list(runner.CAMERAS))

    def test_motion_budget_from_authored_road(self):
        result = placement(200.0, 5.0, 5.0)
        self.assertGreater(result['source_length_m'] - result['projected_end_front_m'], 50.0)
        self.assertEqual(result['physical_motion'], 'unverified')


if __name__ == '__main__':
    unittest.main()
