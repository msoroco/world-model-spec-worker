import json
from pathlib import Path
import unittest

from draft_runner import check as geometry_check, request
from runner import check as capture_check
from signal_source import map_inventory, observed_state
from lane_red_x_meter import measure

class ExactRedXConstruction(unittest.TestCase):
    def test_four_cameras_governance_and_lane_crossing_request(self):
        cfg = json.loads(Path('config.json').read_text())
        geometry = geometry_check(cfg)
        capture = capture_check()
        self.assertTrue(geometry['passed'])
        self.assertTrue(capture['capture']['native_capture_implemented'])
        self.assertFalse(capture['physical_acceptance_claimed'])
        inventory = map_inventory(Path('road.xodr').read_text())
        self.assertEqual(inventory['lane_id'], -1)
        self.assertEqual(inventory['mount_lane_id'], -1)
        cid = cfg['case_id']
        self.assertEqual(request(0, cid)['start_lane_id'], -2)
        if cid.endswith('probe_2'):
            self.assertEqual(request(250, cid)['lateral_speed_mps'], .7)
            self.assertEqual(request(100, cid)['lateral_speed_mps'], 0)
            self.assertEqual(request(301, cid)['lateral_speed_mps'], 0)
        else:
            self.assertEqual(request(250, cid)['lateral_speed_mps'], 0)

    def test_wrong_source_and_timing_rejected(self):
        cfg = json.loads(Path('config.json').read_text())
        cfg['rate_hz'] = 10
        with self.assertRaisesRegex(ValueError, 'timing'):
            geometry_check(cfg)
        with self.assertRaisesRegex(ValueError, '600-frame'):
            request(600, cfg['case_id'])
        class Fake:
            type_id = 'traffic.traffic_light'
            attributes = {'opendrive_signal_id': '100', 'display_role': 'red_x'}
        with self.assertRaisesRegex(ValueError, 'lane-control actor'):
            observed_state(Fake(), map_inventory(Path('road.xodr').read_text()))
        with self.assertRaisesRegex(ValueError, '600 source frames'):
            measure({'frames': []})

if __name__ == '__main__':
    unittest.main()
