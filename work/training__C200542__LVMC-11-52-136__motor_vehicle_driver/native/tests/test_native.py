import json
from pathlib import Path
import unittest

import layout
import runner


class AccessAisleDraftTests(unittest.TestCase):
    def test_premises_and_access_aisle_geometry(self):
        value=layout.check()
        self.assertEqual(value['road_width_m'],10)
        self.assertEqual(value['access_aisle']['y_max_m'],value['adjacent_bay']['y_min_m'])
        self.assertFalse(value['official_designation_proven'])

    def test_original_camera_plan(self):
        value=runner.check()
        self.assertEqual(value['frames'],600)
        self.assertFalse(value['physical_acceptance_claimed'])
        cfg=json.loads(Path('config.json').read_text())
        self.assertEqual(cfg['duration_s'],30)
        self.assertEqual(len(cfg['cameras']),4)
