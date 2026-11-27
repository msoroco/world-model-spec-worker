"""Focused CPU checks for original-frame approach and turn measurement."""

import copy
import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("turn_position", Path(__file__).with_name("turn_position.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def example():
    site = {
        "source_id": "original-map-review", "map_sha256": "a" * 64,
        "public_highway_source": "original-highway-survey",
        "intersection_source": "original-junction-survey",
        "right_lane_design_source": "original-lane-design",
        "qualification_223_4_source": "reviewed-223-4-source",
        "connected_right_exit_source": "original-road-graph",
        "driver_identity_source": "original-driver-packet", "driver_id": "driver-1",
        "entry_road_id": 12, "right_exit_road_id": 14, "junction_id": 8,
        "turn_lane_id": -1, "extreme_right_lane_id": -2,
        "public_highway": True, "non_alley_intersection": True,
        "t_intersection": True, "connected_right_exit": True,
        "right_turn_lane_qualified_under_223_4": True,
    }
    frames = []
    for frame, phase, road, junction in ((0, "approach", 12, None),
                                          (1, "approach", 12, None),
                                          (2, "right_turn", 12, 8),
                                          (3, "right_turn", 12, 8),
                                          (4, "departure", 14, None)):
        frames.append({"original_frame": frame, "time_s": frame / 20,
                       "driver_id": "driver-1", "road_id": road,
                       "lane_id": -1, "junction_id": junction,
                       "phase": phase, "source_ref": "original-lane-frames",
                       "position_xyz_m": [float(frame), 0.0, 0.0]})
    intention = {"maneuver": "right_turn", "source_ref": "original-route-intention",
                 "declared_before_frame": -1}
    return site, frames, intention


class TurnPositionTests(unittest.TestCase):
    def test_both_required_intervals_measured_separately(self):
        site, frames, intention = example()
        measured = MODULE.measure(site, frames, intention)
        self.assertTrue(measured["approach_entirely_from_required_lane"])
        self.assertTrue(measured["turn_entirely_from_required_lane"])
        self.assertIsNone(measured["legal_verdict"])
        frames[0]["lane_id"] = -2
        measured = MODULE.measure(site, frames, intention)
        self.assertFalse(measured["approach_entirely_from_required_lane"])
        self.assertTrue(measured["turn_entirely_from_required_lane"])
        frames[0]["lane_id"] = -1
        frames[2]["lane_id"] = -2
        measured = MODULE.measure(site, frames, intention)
        self.assertTrue(measured["approach_entirely_from_required_lane"])
        self.assertFalse(measured["turn_entirely_from_required_lane"])

    def test_conditional_extreme_right_lane_alternative(self):
        site, frames, intention = example()
        site["right_turn_lane_qualified_under_223_4"] = False
        for row in frames:
            row["lane_id"] = -2
        measured = MODULE.measure(site, frames, intention)
        self.assertFalse(measured["qualifying_right_turn_lane"])
        self.assertEqual(measured["conditional_lane_id"], -2)
        self.assertTrue(measured["approach_entirely_from_required_lane"])
        self.assertTrue(measured["turn_entirely_from_required_lane"])

    def test_missing_qualification_and_timing_rejected(self):
        site, frames, intention = example()
        site["right_turn_lane_qualified_under_223_4"] = None
        with self.assertRaisesRegex(ValueError, "qualification"):
            MODULE.measure(site, frames, intention)
        site["right_turn_lane_qualified_under_223_4"] = True
        intention["declared_before_frame"] = 0
        with self.assertRaisesRegex(ValueError, "before approach"):
            MODULE.measure(site, frames, intention)

    def test_unjoined_driver_exit_and_junction_rejected(self):
        site, frames, intention = example()
        for patch in ({"driver_id": "other"}, {"road_id": 99}, {"source_ref": ""}):
            altered = copy.deepcopy(frames)
            altered[4].update(patch)
            with self.assertRaises(ValueError):
                MODULE.measure(site, altered, intention)
        frames[2]["junction_id"] = None
        with self.assertRaisesRegex(ValueError, "junction"):
            MODULE.measure(site, frames, intention)


if __name__ == "__main__":
    unittest.main()
