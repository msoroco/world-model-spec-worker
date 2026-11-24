import json
from pathlib import Path
import unittest

import layout
import runner


class SchoolTurnDraftTests(unittest.TestCase):
    def test_geometry(self):
        value=layout.check()
        self.assertEqual(value['road_lane_ids'],[1,-1])
        self.assertFalse(value['zone_designation_reviewed'])

    def test_capture(self):
        value=runner.check()
        self.assertEqual(value['frame_count'],600)
        self.assertTrue(value['kinematic_path_only'])
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(len(config['cameras']),4)
