import importlib.util
import pathlib
import unittest


MODULE = pathlib.Path(__file__).resolve().parents[1] / "intersection_geometry.py"
SPEC = importlib.util.spec_from_file_location("intersection_geometry", MODULE)
geometry = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = geometry
SPEC.loader.exec_module(geometry)


class IntersectionGeometryTests(unittest.TestCase):
    def setUp(self):
        self.boundary = geometry.Box(-8.0, -8.0, 8.0, 8.0)

    def test_four_approaches_hit_all_numeric_probes(self):
        for approach in ("east", "west", "north", "south"):
            for feet, branch in ((14, "below_15ft"), (15, "at_15ft"),
                                 (16, "above_15ft")):
                with self.subTest(approach=approach, feet=feet):
                    requested = feet * geometry.FEET_TO_METRES
                    pose = geometry.target_pose(self.boundary, approach,
                                                requested, 4.5, 1.8)
                    corners = geometry.footprint(*pose, 4.5, 1.8)
                    measured = geometry.polygon_gap_to_boundary(corners, self.boundary)
                    self.assertAlmostEqual(measured, requested, places=8)
                    self.assertEqual(geometry.classify_measured_gap(requested), branch)

    def test_footprint_dimensions_change_center_but_preserve_front_gap(self):
        for length in (3.8, 4.5, 5.2):
            pose = geometry.target_pose(self.boundary, "east", 3.0, length, 2.0)
            corners = geometry.footprint(*pose, length, 2.0)
            self.assertAlmostEqual(geometry.polygon_gap_to_boundary(corners, self.boundary), 3.0)

    def test_invalid_dimensions_and_gap_rejected(self):
        with self.assertRaises(ValueError):
            geometry.target_pose(self.boundary, "east", -0.1, 4.5, 1.8)
        with self.assertRaises(ValueError):
            geometry.target_pose(self.boundary, "diagonal", 3.0, 4.5, 1.8)
        with self.assertRaises(ValueError):
            geometry.footprint(0, 0, 0, 0, 1.8)
        with self.assertRaises(ValueError):
            geometry.Box(0, 0, 0, 1)

    def test_measured_inside_intersection_is_zero_gap(self):
        corners = geometry.footprint(0, 0, 0, 4.5, 1.8)
        self.assertEqual(geometry.polygon_gap_to_boundary(corners, self.boundary), 0.0)

    def test_rotated_body_outside_boundary_has_nonzero_gap(self):
        corners = geometry.footprint(15, 15, 45, 4.5, 1.8)
        self.assertGreater(geometry.polygon_gap_to_boundary(corners, self.boundary), 0)


if __name__ == "__main__":
    unittest.main()
