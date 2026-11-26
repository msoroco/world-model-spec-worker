import json
import unittest
from pathlib import Path
from layout import check as layout_check
from runner import check as runner_check


class NativeHose(unittest.TestCase):
    def test_geometry(self):
        self.assertTrue(layout_check()['passed'])
        self.assertFalse(layout_check()['official_way_or_hose_status_proven'])

    def test_case(self):
        cfg = json.loads(Path('config.json').read_text())
        self.assertTrue(runner_check()['passed'])
        self.assertEqual(cfg['case_id'].split('__')[-1], cfg['case_suffix'])
        self.assertEqual(cfg['cross_hose_requested'], cfg['case_suffix'] != 'witness_1')
        self.assertEqual(cfg['consent_record_requested'], cfg['case_suffix'] == 'exception_1_2')
