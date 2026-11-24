import json
import unittest
from pathlib import Path
import runner
class Bundle(unittest.TestCase):
    def test_exact_preflight(self):
        c=json.loads(Path('config.json').read_text())
        p=runner.check(c['case_suffix'],c['candidate_id'])
        self.assertEqual(p['native_route_points']>600,True)
        self.assertEqual(len(p['camera_views']),4)
        self.assertFalse(p['native_imported'])
        self.assertTrue(p['native_capture_pending'])
