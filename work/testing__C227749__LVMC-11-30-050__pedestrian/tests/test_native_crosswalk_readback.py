import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_crosswalk_readback import audit_crosswalk_map


class FakeMap:
    def __init__(self, xodr, points):
        self.xodr = xodr
        self.points = points

    def to_opendrive(self):
        return self.xodr

    def get_crosswalks(self):
        return [SimpleNamespace(x=x, y=y, z=0) for x, y in self.points]


class NativeCrosswalkReadbackTests(unittest.TestCase):
    def setUp(self):
        self.xodr = (ROOT / 'candidate-crossing.xodr').read_text()
        self.scene = json.loads((ROOT / 'cases' / 'outside_right_angle' / 'scene.json').read_text())
        self.points = self.scene['crosswalk_boundaries_xy_m'][0]

    def test_exact_native_vertex_readback(self):
        result = audit_crosswalk_map(self.scene, FakeMap(self.xodr, self.points))
        self.assertEqual(result['native_crosswalk_vertices'], 4)
        self.assertEqual(result['loaded_map_sha256'], self.scene['map_source_sha256'])
        self.assertEqual(result['paint_visibility'], 'unverified')
        self.assertEqual(result['legal_route_classification'], 'unresolved')

    def test_missing_or_shifted_crosswalk_rejected(self):
        with self.assertRaisesRegex(ValueError, 'readback missing'):
            audit_crosswalk_map(self.scene, FakeMap(self.xodr, []))
        points = [[x + 2, y] for x, y in self.points]
        with self.assertRaisesRegex(ValueError, 'absent from Native map'):
            audit_crosswalk_map(self.scene, FakeMap(self.xodr, points))

    def test_changed_map_and_bad_tolerance_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source differs'):
            audit_crosswalk_map(self.scene, FakeMap(self.xodr + ' ', self.points))
        with self.assertRaisesRegex(ValueError, 'tolerance invalid'):
            audit_crosswalk_map(self.scene, FakeMap(self.xodr, self.points), 2)


if __name__ == '__main__':
    unittest.main()
