import json
import unittest
from pathlib import Path
from overpass_source import validate_case
from native_capture import CAMERA_SPECS, camera_placements

class ExactConstruction(unittest.TestCase):
    def test_exact_map_route_and_cameras(self):
        root=Path(__file__).resolve().parents[1]
        scene=json.loads((root/'scene.json').read_text())
        config=json.loads((root/'config.json').read_text())
        self.assertEqual(scene['case_id'],config['selected_case_id'])
        self.assertEqual(config['rate_hz'],20)
        self.assertEqual(config['duration_s'],45.0)
        self.assertEqual(set(camera_placements(scene)),set(CAMERA_SPECS))
        self.assertEqual(validate_case(scene,root/'candidate-overpass.xodr')['deck_z_m'],5)
