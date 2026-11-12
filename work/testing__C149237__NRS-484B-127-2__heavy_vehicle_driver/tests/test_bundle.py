"""Materialized qualifying-truck bundle check; no simulator is contacted."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
from truck_site import GAP_TARGETS_M, initial_pair, validate_motion_envelope
from width_construction import CASES as WIDTH_CASES


class BundleTests(unittest.TestCase):
    def test_exact_identity_and_four_source_camera_contract(self):
        config = json.loads(Path(runner.__file__).with_name('config.json').read_text())
        selected = runner.validate_config(config)['selected_case_id']
        self.assertIn(selected.removeprefix(runner.ASSIGNMENT+'__'), set(GAP_TARGETS_M)|set(WIDTH_CASES))
        self.assertEqual(config['rate_hz'] * config['duration_s'], 900)
        self.assertEqual([item['name'] for item in config['cameras']], list(runner.CAMERAS))

    def test_motion_budget_from_authored_road(self):
        config = json.loads(Path(runner.__file__).with_name('config.json').read_text())
        suffix = config['selected_case_id'].removeprefix(runner.ASSIGNMENT+'__')
        placement = initial_pair(suffix if suffix in GAP_TARGETS_M else 'gap_at_500ft', 5.0, 5.0)
        result = validate_motion_envelope(placement, 5.0)
        self.assertGreater(result['remaining_margin_m'], 50.0)
        self.assertEqual(result['actual_motion'], 'unverified')


if __name__ == '__main__':
    unittest.main()
