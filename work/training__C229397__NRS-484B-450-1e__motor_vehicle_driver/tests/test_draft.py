import json
import unittest
from pathlib import Path
from capture import check

class ExactDraft(unittest.TestCase):
    def test_source_bound(self):
        result=check()
        self.assertTrue(result['passed'])
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_branch_variable(self):
        cfg=json.loads(Path('config.json').read_text())
        suffix=cfg['case_id'].rsplit('__',1)[-1]
        self.assertEqual(cfg['branch'],suffix.rsplit('_',1)[0])
        self.assertIn(cfg['target_variant'],('clear','occupy','absent','present'))
