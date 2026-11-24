import json
from pathlib import Path
import unittest

import geometry
import runner


class ConstructionTests(unittest.TestCase):
    def test_exact_one_way_geometry(self):
        value = geometry.check()
        self.assertTrue(value['passed'])
        self.assertEqual(value['through_lanes'], [-1, -2])
        self.assertEqual(value['lane_widths_m'], [3.5, 3.5])

    def test_bicycle_alternative_and_camera_plan(self):
        value = runner.check()
        self.assertEqual(value['selected_statutory_subject'], 'bicycle')
        self.assertTrue(value['frozen_witness_electric_bicycle_still_pending'])
        self.assertEqual(value['frames'], 600)
        self.assertEqual(len(value['camera_names']), 4)
        self.assertFalse(value['native_imported'])

    def test_exact_config(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['cell_id'], 'C146108')
        self.assertEqual(config['law_id'], 'NRS-484B-270-7b')
        self.assertEqual(config['rider_class'], 'bicycle')
        self.assertEqual(config['duration_s'], 30)
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(len(config['cameras']), 4)


if __name__ == '__main__':
    unittest.main()
