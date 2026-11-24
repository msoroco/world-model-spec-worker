import copy
import json
import unittest
from pathlib import Path
from runner import check, phase_at


class IntersectionRequest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())
        self.road = Path('road.xodr').read_text()

    def test_exact_window_and_controller(self):
        receipt = check(self.config, self.road)
        self.assertEqual(receipt['frames'], 600)
        self.assertFalse(receipt['physical_verified'])
        self.assertEqual(len([phase_at(self.config, i) for i in range(600)]), 600)

    def test_reject_short_or_camera_loss(self):
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaisesRegex(ValueError, 'uncovered'):
            check(bad, self.road)
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'four synchronized'):
            check(bad, self.road)

    def test_reject_wrong_road_context(self):
        bad = copy.deepcopy(self.config)
        bad['one_way_highway'] = True
        with self.assertRaisesRegex(ValueError, 'different statutory'):
            check(bad, self.road)
        with self.assertRaisesRegex(ValueError, 'intersection geometry'):
            check(self.config, '<OpenDRIVE><road id="1"/></OpenDRIVE>')

    def test_reject_invented_results_or_contrast(self):
        bad = copy.deepcopy(self.config)
        bad['physical_verified'] = True
        with self.assertRaisesRegex(ValueError, 'invented'):
            check(bad, self.road)
        bad = copy.deepcopy(self.config)
        bad['control_phases'][1]['target_lane_id'] = '-1' if bad['control_phases'][1]['target_lane_id'] == '1' else '1'
        with self.assertRaisesRegex(ValueError, 'contrast'):
            check(bad, self.road)
