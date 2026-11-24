import json
from pathlib import Path
import unittest

import layout
import runner


class SeparatorDraftTests(unittest.TestCase):
    def test_geometry(self):
        value=layout.check()
        self.assertEqual(value['lane_ids'],[-1,-2])
        self.assertEqual(value['separator']['form'],'solid')
        self.assertFalse(value['public_highway_and_access_authority_reviewed'])

    def test_capture(self):
        value=runner.check()
        self.assertEqual(value['frame_count'],600)
        self.assertFalse(value['physical_acceptance_claimed'])
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(len(config['cameras']),4)
