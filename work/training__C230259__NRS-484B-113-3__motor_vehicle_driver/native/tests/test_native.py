import json
from pathlib import Path
import unittest

import layout
import runner


class BackingDraftTests(unittest.TestCase):
    def test_geometry(self):
        value=layout.check()
        self.assertEqual(value['road_width_m'],9)
        self.assertFalse(value['section_stem_recovered'])

    def test_capture(self):
        value=runner.check()
        self.assertEqual(value['frame_count'],600)
        self.assertFalse(value['physical_acceptance_claimed'])
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(len(config['cameras']),4)
