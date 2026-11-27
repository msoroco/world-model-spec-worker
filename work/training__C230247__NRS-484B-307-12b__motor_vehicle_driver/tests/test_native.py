"""CPU regression for the red-X pair's exact source-bound metering."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from signal_source import map_inventory
from lane_red_x_meter import measure

class RedXPackageTest(unittest.TestCase):
    def test_both_exact_cases_and_governed_lane(self):
        inventory = map_inventory((ROOT / 'native/road.xodr').read_text())
        self.assertEqual(inventory['lane_id'], -1)
        for tag, lane in (('1', -2), ('2', -1)):
            config = ROOT / ('config.json' if tag == '1' else 'cases/probe_2/config.json')
            value = json.loads(config.read_text())
            self.assertEqual(value['case']['target_lane_id'], lane)
            self.assertEqual(value['rate_hz'] * value['duration_s'], 600)
            self.assertEqual(len(value['cameras']), 4)
    def test_missing_original_frames_rejected(self):
        with self.assertRaisesRegex(ValueError, '600 source frames'):
            measure({'frames': []})

if __name__ == '__main__':
    unittest.main()
