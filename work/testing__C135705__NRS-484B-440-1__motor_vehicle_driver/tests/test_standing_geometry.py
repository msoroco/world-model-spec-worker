import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from standing_geometry import (STATUTORY_SIGHT_DISTANCE_M, measure,
                               segment_crosses_rect)


def scene():
    return {"paved_road_xy_m": [-80,-3.5,80,3.5],
            "standing_body_xy_m": [-2.5,-3.5,2.5,-1.5],
            "standing_side": "negative_y",
            "other_vehicle_centers_xy_m": [[-65,2.2],[-10,2.2],[0,2.2],[10,2.2],[65,2.2]],
            "other_vehicle_half_length_m": 2.5,
            "other_vehicle_half_width_m": 1.0,
            "sight_eye_y_m": 2.2,
            "sight_probe_distances_m": [60.0,60.96,61.9],
            "sight_occluders_xy_m": []}


class StandingGeometryTests(unittest.TestCase):
    def test_exact_200_feet_and_two_direction_probes(self):
        self.assertAlmostEqual(STATUTORY_SIGHT_DISTANCE_M,60.96)
        observed=measure(scene())
        self.assertEqual(len(observed["sight_probes"]),6)
        self.assertTrue(all(p["visible"] for p in observed["sight_probes"].values()))
        self.assertEqual(observed["unobstructed_opposite_width_m"],5)
        self.assertTrue(observed["physical_passage_observed"])
        self.assertEqual(observed["legal_adequacy_judgment"],"unresolved")

    def test_narrow_standing_footprint_blocks_full_body_passage(self):
        value=scene();value["standing_body_xy_m"]=[-2.5,-.1,2.5,1.9]
        observed=measure(value)
        self.assertAlmostEqual(observed["unobstructed_opposite_width_m"],1.6)
        self.assertIn(2,observed["passing_body_collision_frames"])
        self.assertFalse(observed["physical_passage_observed"])

    def test_actual_occluder_blocks_both_200_foot_views(self):
        value=scene();value["sight_occluders_xy_m"]=[[-31,-.5,-29,.3],[29,-.5,31,.3]]
        observed=measure(value)
        self.assertFalse(observed["sight_probes"]["negative_x:60.960m"]["visible"])
        self.assertFalse(observed["sight_probes"]["positive_x:60.960m"]["visible"])

    def test_segment_touch_and_invalid_geometry_rejected(self):
        self.assertTrue(segment_crosses_rect((-2,0),(2,0),[-1,0,1,1]))
        self.assertFalse(segment_crosses_rect((-2,-1),(2,-1),[-1,0,1,1]))
        value=scene();value["standing_body_xy_m"]=[2,0,-2,1]
        with self.assertRaisesRegex(ValueError,"invalid finite rectangle"):
            measure(value)

    def test_authored_case_pairs_hold_fixed_conditions(self):
        folder=Path(__file__).resolve().parents[1]/"cases"
        values={suffix:json.loads((folder/suffix/"scene.json").read_text())
                for suffix in ("passage_clear_view","passage_blocked","view_occluded_both")}
        clear,blocked,occluded=(values[x] for x in values)
        self.assertEqual(clear["other_vehicle_centers_xy_m"],blocked["other_vehicle_centers_xy_m"])
        self.assertEqual(clear["sight_occluders_xy_m"],blocked["sight_occluders_xy_m"])
        self.assertEqual(clear["standing_body_xy_m"],occluded["standing_body_xy_m"])
        self.assertEqual(clear["other_vehicle_centers_xy_m"],occluded["other_vehicle_centers_xy_m"])
        self.assertEqual([measure(x)["physical_passage_observed"] for x in (clear,blocked,occluded)],
                         [True,False,True])
        self.assertEqual([measure(x)["sight_probes"]["negative_x:60.960m"]["visible"]
                          for x in (clear,blocked,occluded)],[True,True,False])


if __name__ == "__main__":unittest.main()
