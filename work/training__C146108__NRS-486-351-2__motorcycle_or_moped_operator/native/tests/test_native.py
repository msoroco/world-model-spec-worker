import json
from pathlib import Path
import unittest

import geometry
import runner


class SameLaneDraftTests(unittest.TestCase):
    def test_two_lanes_and_width(self):
        details = geometry.check()
        self.assertEqual(details['road_length_m'], 300)
        self.assertEqual(details['through_lanes'], [-1, -2])
        self.assertEqual(details['lane_widths_m'], [6.0, 6.0])

    def test_original_camera_and_duration_plan(self):
        details = runner.check()
        self.assertEqual(details['selected_statutory_subject'], 'motorcycle')
        self.assertEqual(details['frames'], 600)
        self.assertEqual(len(details['camera_names']), 4)
        self.assertFalse(details['physical_acceptance_claimed'])

    def test_same_lane_design(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['law_id'], 'NRS-486-351-2')
        self.assertEqual(config['cell_id'], 'C146108')
        self.assertEqual(config['rider_class'], 'motorcycle')
        self.assertEqual(config['duration_s'], 30)
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(len(config['cameras']), 4)


if __name__ == '__main__':
    unittest.main()
