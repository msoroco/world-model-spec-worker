"""CPU construction checks for both lane phases and the conditional alternative."""

import importlib.util
import unittest
from pathlib import Path

from test_turn_position import example


SPEC = importlib.util.spec_from_file_location("native_turn_construction", Path(__file__).with_name("native_turn_construction.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def site_with_routes():
    site, _, _ = example()
    site.update({
        "intended_maneuver": {"maneuver": "right_turn", "source_ref": "original-intention"},
        "native_spawn": {"source_id": "original-spawn", "blueprint_id": "vehicle.car",
                         "pose_xyz_ypr": [0, 0, 0, 0, 0, 0]},
        "trajectories": {
            "turn": {"source_ref": "original-turn-route", "xy": [[0, 0], [4, 0], [8, -4]]},
            "extreme": {"source_ref": "original-extreme-route", "xy": [[0, 3], [4, 3], [8, -1]]},
        },
        "source_confirmed_lane_change_feasible": True,
    })
    return site


class NativeTurnConstructionTests(unittest.TestCase):
    def test_five_exact_variants_preserve_distinct_phase_lanes(self):
        aid = MODULE.AID
        site = site_with_routes()
        expected = {
            "lane_both_intervals": (-1, -1),
            "approach_from_other_lane": (-2, -1),
            "turn_from_other_lane": (-1, -2),
            "other_lane_both_intervals": (-2, -2),
        }
        for suffix, lane_pair in expected.items():
            with self.subTest(suffix=suffix):
                request = MODULE.construct(site, aid + "__" + suffix)
                self.assertEqual((request["approach_lane_id"], request["turn_lane_id"]), lane_pair)
                self.assertEqual(len(request["trajectory_sources"]), 2)
        site["right_turn_lane_qualified_under_223_4"] = False
        request = MODULE.construct(site, aid + "__extreme_right_no_qualifying_lane")
        self.assertFalse(request["conditional_lane_qualification"])
        self.assertEqual((request["approach_lane_id"], request["turn_lane_id"]), (-2, -2))

    def test_unsupported_case_and_unsourced_lane_change_rejected(self):
        site = site_with_routes()
        with self.assertRaisesRegex(ValueError, "unsupported exact"):
            MODULE.construct(site, MODULE.AID + "__unknown")
        site["source_confirmed_lane_change_feasible"] = False
        with self.assertRaisesRegex(ValueError, "lane change"):
            MODULE.construct(site, MODULE.AID + "__approach_from_other_lane")
        site["source_confirmed_lane_change_feasible"] = True
        site["trajectories"]["turn"]["source_ref"] = ""
        with self.assertRaisesRegex(ValueError, "trajectory"):
            MODULE.construct(site, MODULE.AID + "__lane_both_intervals")


if __name__ == "__main__":
    unittest.main()
