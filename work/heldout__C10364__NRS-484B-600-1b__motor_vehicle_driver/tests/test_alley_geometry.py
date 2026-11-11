import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / "alley_geometry.py"
spec = importlib.util.spec_from_file_location("alley_geometry", MODULE)
geometry = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = geometry
spec.loader.exec_module(geometry)


class AlleyGeometryTest(unittest.TestCase):
    def build(self, start, end, **changes):
        knobs = dict(alley_width=6.0, vehicle_width=1.8,
                     pedestrian_station=12.0, pedestrian_offset=2.0,
                     property_station=15.0, property_offset=-2.0)
        knobs.update(changes)
        return geometry.plan_alley(geometry.Point(*start), geometry.Point(*end), **knobs)

    def test_both_approach_directions_place_objects_on_opposite_world_sides(self):
        east = self.build((0, 0), (30, 0))
        west = self.build((30, 0), (0, 0))
        self.assertEqual((east.pedestrian.x, east.pedestrian.y), (12, 2))
        self.assertEqual((west.pedestrian.x, west.pedestrian.y), (18, -2))
        self.assertEqual(east.pedestrian_route_gap, west.pedestrian_route_gap)
        self.assertGreater(east.property_route_gap, 0)

    def test_rejects_unrealized_or_unsafe_placement(self):
        with self.assertRaisesRegex(ValueError, "overlaps"):
            self.build((0, 0), (30, 0), pedestrian_offset=1.0)
        with self.assertRaisesRegex(ValueError, "boundary"):
            self.build((0, 0), (30, 0), property_offset=-2.8)
        with self.assertRaisesRegex(ValueError, "outside the usable route"):
            self.build((0, 0), (30, 0), pedestrian_station=31)
        with self.assertRaisesRegex(ValueError, "too narrow"):
            self.build((0, 0), (30, 0), alley_width=2)

    def test_rotation_preserves_alley_relative_placement(self):
        north = self.build((5, 5), (5, 35))
        self.assertEqual((north.pedestrian.x, north.pedestrian.y), (3, 17))
        self.assertEqual((north.property_center.x, north.property_center.y), (7, 20))


if __name__ == "__main__":
    unittest.main()
