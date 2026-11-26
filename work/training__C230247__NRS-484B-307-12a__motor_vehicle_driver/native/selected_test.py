import json
from pathlib import Path
import unittest

import runner
from draft_runner import request
from signal_source import map_inventory


class SelectedConstruction(unittest.TestCase):
    def test_exact_capture_and_source_gate(self):
        report=runner.check()
        self.assertTrue(report['capture']['native_capture_implemented'])
        self.assertFalse(report['capture']['physical_acceptance_claimed'])
        cfg=json.loads(Path('config.json').read_text())
        plan=request(300,cfg['case_id'])
        self.assertEqual(plan['target_lane_id'],cfg['case']['target_lane_id'])
        inventory=map_inventory(Path('road.xodr').read_text())
        self.assertEqual(inventory['lane_id'],-1)
        self.assertTrue(inventory['official_authority_review_pending'])

    def test_invalid_lane_or_camera_rejected(self):
        cfg=json.loads(Path('config.json').read_text())
        cfg['cameras'].pop()
        with self.assertRaises(ValueError):
            from capture import check
            check(cfg,Path('road.xodr').read_text())


if __name__=='__main__':
    unittest.main()
