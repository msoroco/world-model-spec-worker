import copy
import importlib.util
import hashlib
import json
import pathlib
import tempfile
import unittest


MODULE = pathlib.Path(__file__).resolve().parents[1] / "roundabout.py"
SPEC = importlib.util.spec_from_file_location("roundabout", MODULE)
ROUNDABOUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUNDABOUT)
RUN_SPEC = importlib.util.spec_from_file_location("roundabout_runner", MODULE.with_name("runner.py"))
RUNNER = importlib.util.module_from_spec(RUN_SPEC)
RUN_SPEC.loader.exec_module(RUNNER)


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
            "actor_id": "ego-17", "intended_departure": "opposite_direction",
            "vehicle_blueprint": "vehicle.test", "entry_id": "south-entry", "exit_id": "north-exit",
            "controller_sha256": "b"*64, "weather_sha256": "c"*64,
            "camera_plan_sha256": "d"*64, "frames": frames}


class TestRoundabout(unittest.TestCase):
    def test_sealed_source_hash_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "map.json"
            path.write_text(json.dumps(topology_source()))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(ROUNDABOUT.load_sealed_json(path, digest)["map_id"], "test-map")
            with self.assertRaisesRegex(ROUNDABOUT.SourceError, "source hash mismatch"):
                ROUNDABOUT.load_sealed_json(path, "0"*64)

    def test_runner_constructs_and_cleans_up(self):
        class Adapter:
            def __init__(self):
                self.controls = []
                self.destroyed = False
                self.lane_id = "lane-inner"

            def readback_map(self):
                return topology_source()

            def spawn_motor_vehicle(self, position):
                self.spawned_at = position
                return "ego-17"

            def actor_state(self, actor):
                return {"x": -5, "y": -2, "heading_x": 1, "heading_y": 0}

            def step(self, actor, control):
                i = len(self.controls)
                self.controls.append(control)
                section = "entry" if i < 200 else "ring" if i <= 600 else "exit"
                return {"frame": i, "time_s": round(i*0.05, 4), "section": section,
                        "lane_id": self.lane_id, "actor_id": actor, "heading_x": -1, "heading_y": 0}

            def seal(self, case_id, topology, frames):
                value = history(self.lane_id, case_id)
                value["frames"] = frames
                return value

            def destroy(self, actor):
                self.destroyed = True

        adapter = Adapter()
        result = RUNNER.execute(adapter, "left-case", "left")
        self.assertEqual(len(adapter.controls), 900)
        self.assertTrue(adapter.destroyed)
        self.assertTrue(result["requested_lane_observed"])

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

    def test_comparison_rejects_changed_controller(self):
        source = topology_source()
        left = ROUNDABOUT.verify_topology(source, "left")
        outer = ROUNDABOUT.verify_topology(source, "outer")
        a = ROUNDABOUT.verify_original_history(history("lane-inner", "left-case"), left, "left-case")
        changed = history("lane-outer", "outer-case")
        changed["controller_sha256"] = "e"*64
        b = ROUNDABOUT.verify_original_history(changed, outer, "outer-case")
        with self.assertRaisesRegex(ROUNDABOUT.SourceError, "fixed conditions"):
            ROUNDABOUT.compare(a, b)


if __name__ == "__main__":
    unittest.main()
