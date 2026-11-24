import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check_scene


class CrosswalkMapConstructionTests(unittest.TestCase):
    def test_both_authored_crosswalk_placements_match_their_cases(self):
        for name, map_name in (
            ('outside_right_angle', 'candidate-crossing.xodr'),
            ('outside_neither', 'candidate-crossing.xodr'),
            ('inside_crosswalk_oblique', 'candidate-crossing-inside.xodr'),
        ):
            scene_path = ROOT / 'cases' / name / 'scene.json'
            map_path = ROOT / map_name
            scene = check_scene(scene_path, map_path)
            self.assertEqual(scene['map_source_sha256'], hashlib.sha256(map_path.read_bytes()).hexdigest())

    def test_opposite_crosswalk_placement_rejected(self):
        scene_path = ROOT / 'cases' / 'inside_crosswalk_oblique' / 'scene.json'
        with self.assertRaisesRegex(ValueError, 'source-hashed exact OpenDRIVE differs'):
            check_scene(scene_path, ROOT / 'candidate-crossing.xodr')


if __name__ == '__main__':
    unittest.main()
