import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geometry import Rectangle, audit_design, construct


class ConstructionTests(unittest.TestCase):
    def test_clear_area_uses_intervening_area(self):
        scene = construct("clear")
        self.assertFalse(audit_design(scene)["designated_lane_used"])

    def test_blocked_area_constructs_barrier_and_uses_designated_lane(self):
        scene = construct("blocked", area_blocked=True)
        self.assertEqual(audit_design(scene)["obstacle_count"], 2)

    def test_opposite_travel_preserves_bypass(self):
        scene = construct("opposite", direction=-1, area_blocked=True)
        self.assertTrue(audit_design(scene)["designated_lane_used"])
        self.assertGreater(scene.route[0][0], scene.route[-1][0])

    def test_later_return_is_caused_by_longer_sidewalk_obstruction(self):
        early = construct("early", area_blocked=True)
        late = construct("late", area_blocked=True, sidewalk_end=40)
        self.assertEqual(late.obstacles[0].x1 - early.obstacles[0].x1, 6)
        self.assertEqual(late.route[-2][0] - early.route[-2][0], 6)
        audit_design(late)

    def test_missing_section_is_distinct_constructed_kind(self):
        scene = construct("missing", obstruction_kind="missing_section")
        self.assertEqual(audit_design(scene)["obstruction_kind"], "missing_section")
        self.assertEqual(len(scene.obstacles), 0)
        self.assertEqual(len(scene.missing_sections), 1)

    def test_route_crossing_barrier_is_rejected(self):
        scene = construct("bad", area_blocked=True)
        bad = replace(scene, route=((10, 5), (17, 5), (18, 3), (36, 3), (37, 5), (50, 5)))
        with self.assertRaisesRegex(ValueError, "intersects"):
            audit_design(bad)

    def test_missing_barrier_is_rejected(self):
        scene = construct("bad", area_blocked=True)
        with self.assertRaisesRegex(ValueError, "barrier"):
            audit_design(replace(scene, obstacles=scene.obstacles[:1]))

    def test_misaligned_designated_lane_is_rejected(self):
        scene = construct("bad", area_blocked=True)
        with self.assertRaisesRegex(ValueError, "border"):
            audit_design(replace(scene, designated_lane=Rectangle("lane", 0, 60, -2, 0)))


if __name__ == "__main__":
    unittest.main()
