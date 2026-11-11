import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import CASE, validate_config
from camera_setup import PROFILE


class BundleTests(unittest.TestCase):
    def test_exact_case_and_four_original_cameras(self):
        config=validate_config(json.loads((ROOT/'config.json').read_text()))
        self.assertEqual(config['selected_case_id'],CASE)
        self.assertEqual([row['name'] for row in config['cameras']],list(PROFILE))
        self.assertEqual(config['physical_completion']['criterion'],'turn')
        self.assertEqual(config['physical_completion']['body_key'],'ego.body_vertices_xy_m')


if __name__=='__main__':unittest.main()
