"""Offline exact-source check for a branch Native request bundle."""
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parents[1]


class ExactBranchRequest(unittest.TestCase):
    def test_authored_source_and_identity(self):
        cfg=json.loads((HERE/'config.json').read_text())
        if cfg['case_id'].rsplit('__',1)[1].startswith('signal_'):
            from signal_check import check
        else:
            from officer_check import check
        result=check(HERE)
        self.assertEqual(result['case_id'],cfg['case_id'])
        self.assertEqual(result['frames'],600)
        self.assertIs(result['original_native_observed'],False)

    def test_required_source_windows(self):
        cfg=json.loads((HERE/'config.json').read_text())
        rows=(HERE/'requested-tracks.jsonl').read_text().splitlines()
        self.assertEqual(len(rows),cfg['frames'])
        self.assertEqual(cfg['rate_hz'],20)
        self.assertEqual(cfg['duration_s'],30)


if __name__=='__main__':unittest.main()
