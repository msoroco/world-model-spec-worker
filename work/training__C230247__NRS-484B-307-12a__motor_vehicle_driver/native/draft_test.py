import json
from pathlib import Path
import unittest
from runner import check, request

class Draft(unittest.TestCase):
    def test_exact_bundle(self):
        cfg=json.loads(Path('config.json').read_text())
        result=check(cfg)
        self.assertEqual(result['frames'],600)
        self.assertEqual(result['signal_valid_lane_id'],-1)
        self.assertEqual(result['target_lane_id'], -2 if cfg['case_id'].endswith('other_lane') else -1)
    def test_reject_wrong_identity_and_time(self):
        cfg=json.loads(Path('config.json').read_text())
        cfg['law_id']='NRS-484B-307-12b'
        with self.assertRaisesRegex(ValueError,'frozen identity'):
            check(cfg)
        with self.assertRaisesRegex(ValueError,'600-frame'):
            request(600,cfg['case_id'])
if __name__=='__main__': unittest.main()
