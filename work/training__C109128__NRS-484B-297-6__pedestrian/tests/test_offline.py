import json
import unittest
from pathlib import Path
from native_scene import check, request, geometry, FRAMES, CAMERAS

class ExactBypassOffline(unittest.TestCase):
    def test_exact_identity_and_geometry(self):
        cfg = json.loads(Path('config.json').read_text())
        self.assertTrue(check(cfg['case_suffix'])['passed'])
        self.assertEqual(cfg['case_id'], cfg['selected_case_id'])
        self.assertEqual(cfg['case_id'], cfg['case']['case_id'])
        self.assertEqual((cfg['cell_id'], cfg['law_id'], cfg['actor']),
                         ('C109128', 'NRS-484B-297-6', 'pedestrian'))
        self.assertEqual((cfg['rate_hz'], cfg['duration_s']), (20, 30))
        self.assertEqual(len(cfg['cameras']), len(CAMERAS))
        self.assertEqual(request(cfg['case_suffix'], FRAMES - 1)['target_xy_m'][1],
                         geometry(cfg['case_suffix'])['sidewalk_center_y'])
        self.assertIn(cfg['candidate_id'], ('primary', 'fallback1'))
