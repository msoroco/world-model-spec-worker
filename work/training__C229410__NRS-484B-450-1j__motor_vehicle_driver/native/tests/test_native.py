import json
from pathlib import Path
import unittest

import layout
import runner


class FireStationDraftTests(unittest.TestCase):
    def test_geometry(self):
        value=layout.check()
        self.assertEqual(value['twenty_feet_m'],6.096)
        self.assertFalse(value['official_station_identity_reviewed'])

    def test_capture(self):
        value=runner.check()
        self.assertEqual(value['frame_count'],600)
        self.assertFalse(value['physical_acceptance_claimed'])
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(len(config['cameras']),4)
