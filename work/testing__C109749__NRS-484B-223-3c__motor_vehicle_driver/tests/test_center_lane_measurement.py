import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("center_lane_measurement", ROOT / "center_lane_measurement.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def packet(distance_m=15.24, merge=True):
    samples = [
        {"frame": 100, "body_centre_xy_m": [0, 0], "lane": "approach", "left_turn_onto_highway_complete": False},
        {"frame": 101, "body_centre_xy_m": [1, 0], "lane": "shared_center_turn", "left_turn_onto_highway_complete": True},
        {"frame": 102, "body_centre_xy_m": [1 + distance_m / 2, 0], "lane": "shared_center_turn"},
        {"frame": 103, "body_centre_xy_m": [1 + distance_m, 0], "lane": "receiving_through" if merge else "shared_center_turn", "merged_into_through_lane": merge},
    ]
    return {"source": {"path": "native/trace.json", "sha256": "a" * 64},
            "highway_context_source": {"path": "review/highway.json", "sha256": "b" * 64},
            "lane_design_source": {"path": "native/lanes.json", "sha256": "c" * 64},
            "lane_design": "single_shared_bidirectional_center_turn_only", "samples": samples}


class MeasurementTests(unittest.TestCase):
    def test_numeric_boundary_probes(self):
        for metres, relation in [(14.94, -1), (15.24, 0), (15.54, 1)]:
            measured = MODULE.measure_center_lane_distance(packet(metres))
            self.assertEqual(measured["merge_frame"], 103)
            self.assertAlmostEqual(measured["distance_ft"], metres * MODULE.FEET_PER_METRE)
            difference = measured["distance_ft"] - measured["boundary_ft"]
            self.assertEqual((difference > 0) - (difference < 0), relation)

    def test_missing_merge_is_censored(self):
        measured = MODULE.measure_center_lane_distance(packet(15.54, merge=False))
        self.assertTrue(measured["censored"])
        self.assertIsNone(measured["merge_frame"])

    def test_missing_context_rejected(self):
        p = packet()
        del p["highway_context_source"]
        with self.assertRaisesRegex(ValueError, "highway_context_source"):
            MODULE.measure_center_lane_distance(p)

    def test_fake_shared_lane_rejected(self):
        p = packet()
        p["lane_design"] = "ordinary_center_lane"
        with self.assertRaisesRegex(ValueError, "unverified shared"):
            MODULE.measure_center_lane_distance(p)

    def test_untracked_exit_rejected(self):
        p = packet()
        p["samples"][2]["lane"] = "receiving_through"
        with self.assertRaisesRegex(ValueError, "untracked center lane exit"):
            MODULE.measure_center_lane_distance(p)

    def test_multiple_turn_events_rejected(self):
        p = packet()
        p["samples"][2]["left_turn_onto_highway_complete"] = True
        with self.assertRaisesRegex(ValueError, "exactly one"):
            MODULE.measure_center_lane_distance(p)

    def test_duplicate_or_pre_turn_merge_event_rejected(self):
        p = packet()
        p["samples"].append({"frame": 104, "body_centre_xy_m": [18, 0],
                             "lane": "receiving_through", "merged_into_through_lane": True})
        with self.assertRaisesRegex(ValueError, "merge event must occur once"):
            MODULE.measure_center_lane_distance(p)
        p = packet()
        p["samples"][0]["merged_into_through_lane"] = True
        with self.assertRaisesRegex(ValueError, "merge event must occur once"):
            MODULE.measure_center_lane_distance(p)

    def test_invalid_frame_and_position_rejected(self):
        p = packet()
        p["samples"][2]["frame"] = 101
        with self.assertRaisesRegex(ValueError, "contiguous"):
            MODULE.measure_center_lane_distance(p)
        p = packet()
        p["samples"][2]["body_centre_xy_m"] = [float("nan"), 0]
        with self.assertRaisesRegex(ValueError, "non-finite"):
            MODULE.measure_center_lane_distance(p)


if __name__ == "__main__":
    unittest.main()
