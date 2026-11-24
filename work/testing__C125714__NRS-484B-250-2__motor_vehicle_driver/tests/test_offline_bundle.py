"""Exact materialized C125714 scene checks for runtime.py offline."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check_scene


class OfflineCase(unittest.TestCase):
    def test_two_connected_approaches_and_four_cameras(self):
        scene, road = check_scene(ROOT / 'scene.json')
        self.assertEqual(road.name, 'candidate-map.xodr')
        self.assertEqual(scene['ego_side'], 'left')
        self.assertEqual(scene['other_side'], 'right')
        self.assertEqual(scene['capture_rate_hz'], 20)
        self.assertEqual([c['name'] for c in scene['cameras']],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])

    def test_wrong_case_and_device_claim_rejected(self):
        scene = json.loads((ROOT / 'scene.json').read_text())
        wrong = copy.deepcopy(scene)
        wrong['case_id'] = scene['case_id'] + '__unselected'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(ROOT / 'candidate-map.xodr', root / 'candidate-map.xodr')
            (root / 'wrong-scene.json').write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'wrong exact'):
                check_scene(root / 'wrong-scene.json')


if __name__ == '__main__':
    unittest.main()
