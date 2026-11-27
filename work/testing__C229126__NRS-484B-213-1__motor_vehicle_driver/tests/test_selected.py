import json
import unittest
from pathlib import Path
from native_scene import ASSIGNMENT, CASE_VARIANTS, CAMERAS

class SelectedBundleTest(unittest.TestCase):
    def test_exact_case_and_four_cameras(self):
        cfg=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
        self.assertEqual(cfg['assignment_id'],ASSIGNMENT)
        self.assertIn(cfg['selected_case_id'].removeprefix(ASSIGNMENT+'__'),CASE_VARIANTS)
        self.assertEqual([c['name'] for c in cfg['cameras']],list(CAMERAS))

if __name__=='__main__': unittest.main()
