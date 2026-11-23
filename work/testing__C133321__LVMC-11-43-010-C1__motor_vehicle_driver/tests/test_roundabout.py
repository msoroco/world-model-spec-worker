import copy
import importlib.util
import pathlib
import unittest


MODULE = pathlib.Path(__file__).resolve().parents[1] / "roundabout.py"
SPEC = importlib.util.spec_from_file_location("roundabout", MODULE)
ROUNDABOUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUNDABOUT)


def topology_source():
    def lane(lane_id, radius):
        return {"lane_id": lane_id, "sample0": {"x": 0, "y": -radius},
                "sample1": {"x": 1, "y": -radius}, "route": [
                    {"x": -radius-2, "y": -radius, "section": "entry", "lane_id": lane_id},
                    {"x": 0, "y": -radius, "section": "ring", "lane_id": lane_id},
                    {"x": radius*0.7071, "y": -radius*0.7071, "section": "ring", "lane_id": lane_id},
                    {"x": radius, "y": 0, "section": "ring", "lane_id": lane_id},
                    {"x": radius*0.7071, "y": radius*0.7071, "section": "ring", "lane_id": lane_id},
                    {"x": 0, "y": radius, "section": "ring", "lane_id": lane_id},
                    {"x": -radius-2, "y": radius, "section": "exit", "lane_id": lane_id}]}
    return {"source_kind": "native_map_readback", "layout": "multilane_roundabout",
            "jurisdiction": "Las Vegas, Nevada", "map_id": "test-map", "map_sha256": "a"*64,
            "center": {"x": 0, "y": 0}, "entry": {"prior": {"x": -8, "y": -3},
            "junction": {"x": -4, "y": -3}}, "exit": {"junction": {"x": -4, "y": 3},
            "after": {"x": -8, "y": 3}},
            "lanes": {"left": lane("lane-inner", 2), "outer": lane("lane-outer", 4)}}


def history(lane_id, case_id):
    frames = []
    for i in range(900):
        section = "entry" if i < 200 else "ring" if i <= 600 else "exit"
        frames.append({"frame": i, "time_s": round(i*0.05, 4), "section": section,
                       "lane_id": lane_id, "actor_id": "ego-17", "heading_x": -1, "heading_y": 0})
    return {"source_kind": "sealed_native_original_history", "case_id": case_id,
            "map_id": "test-map", "map_sha256": "a"*64, "actor_role": "motor_vehicle_driver",
            "actor_id": "ego-17", "intended_departure": "opposite_direction", "frames": frames}


class TestRoundabout(unittest.TestCase):
    def test_both_allocated_lanes_and_comparison(self):
        source = topology_source()
        left = ROUNDABOUT.verify_topology(source, "left")
        outer = ROUNDABOUT.verify_topology(source, "outer")
        a = ROUNDABOUT.verify_original_history(history("lane-inner", "left-case"), left, "left-case")
        b = ROUNDABOUT.verify_original_history(history("lane-outer", "outer-case"), outer, "outer-case")
        self.assertTrue(a["requested_lane_observed"] and b["requested_lane_observed"])
        self.assertTrue(ROUNDABOUT.compare(a, b)["both_departures_observed"])

    def test_left_lateral_readback_rejected(self):
        source = topology_source()
        source["lanes"]["left"]["sample0"] = {"x": 0, "y": -5}
        with self.assertRaisesRegex(ROUNDABOUT.SourceError, "not left"):
            ROUNDABOUT.verify_topology(source, "left")

    def test_disconnected_route_rejected(self):
        source = topology_source()
        source["lanes"]["outer"]["route"][3]["x"] = 100
        with self.assertRaises(ROUNDABOUT.SourceError):
            ROUNDABOUT.verify_topology(source, "outer")

    def test_unfinished_circular_route_rejected(self):
        source = topology_source()
        source["lanes"]["left"]["route"][5]["x"] = 1.8
        source["lanes"]["left"]["route"][5]["y"] = 0.8
        with self.assertRaises(ROUNDABOUT.SourceError):
            ROUNDABOUT.verify_topology(source, "left")

    def test_original_frame_gap_rejected(self):
        lane = ROUNDABOUT.verify_topology(topology_source(), "left")
        original = history("lane-inner", "left-case")
        original["frames"][30]["frame"] = 31
        with self.assertRaisesRegex(ROUNDABOUT.SourceError, "discontinuity"):
            ROUNDABOUT.verify_original_history(original, lane, "left-case")

    def test_wrong_actor_or_map_rejected(self):
        lane = ROUNDABOUT.verify_topology(topology_source(), "left")
        original = history("lane-inner", "left-case")
        wrong = copy.deepcopy(original)
        wrong["frames"][550]["actor_id"] = "other"
        with self.assertRaisesRegex(ROUNDABOUT.SourceError, "actor changed"):
            ROUNDABOUT.verify_original_history(wrong, lane, "left-case")
        wrong = copy.deepcopy(original)
        wrong["map_sha256"] = "b"*64
        with self.assertRaisesRegex(ROUNDABOUT.SourceError, "map source mismatch"):
            ROUNDABOUT.verify_original_history(wrong, lane, "left-case")

    def test_missing_departure_and_lane_switch_visible(self):
        lane = ROUNDABOUT.verify_topology(topology_source(), "left")
        original = history("lane-inner", "left-case")
        original["frames"][300]["lane_id"] = "lane-outer"
        result = ROUNDABOUT.verify_original_history(original, lane, "left-case")
        self.assertTrue(result["other_ring_lane_observed"])
        wrong = history("lane-inner", "left-case")
        for frame in wrong["frames"]:
            frame["section"] = "ring"
        with self.assertRaisesRegex(ROUNDABOUT.SourceError, "traversal absent"):
            ROUNDABOUT.verify_original_history(wrong, lane, "left-case")


if __name__ == "__main__":
    unittest.main()
