"""Materialized exact case checks; no CARLA or physical claim."""
import json
from pathlib import Path
import unittest
from runner import check_bundle
from crossing_geometry import validate_scene

class OfflineBundleTests(unittest.TestCase):
    def test_exact_bundle(self):
        root=Path(__file__).resolve().parents[1]
        scene=json.loads((root/'scene.json').read_text())
        config=json.loads((root/'config.json').read_text())
        self.assertEqual(check_bundle(root)['case_id'],config['selected_case_id'])
        self.assertEqual(config['duration_s'],20)
        self.assertEqual(config['required_atoms'],[])
        self.assertEqual(config['source_packets'],[])
        self.assertGreater(validate_scene(scene)['route_length_m'],5)

if __name__=='__main__': unittest.main()
