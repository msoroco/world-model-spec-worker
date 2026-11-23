"""Exercise source-cited observation extraction from original Native bodies."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_observation import plan, from_frame
from native_runner import run_carla_with_plan
from tests.test_source_bound_scene import fixture
from tests.test_native_frame import Actor, World


def body(x, y):
    return {"location_xyz_m": [x, y, 0], "velocity_xyz_mps": [0, 0, 0],
            "body_vertices_xyz_m": [[x - .5, y - .5, 0], [x + .5, y - .5, 0],
                                    [x + .5, y + .5, 0], [x - .5, y + .5, 0]]}


def observation_packet(root):
    packet = fixture(root)
    citation = {"source_citation": "synthetic CPU geometry", "reviewer": "CPU test"}
    packet["observation_plan"] = {
        "pedestrian_zone": {**citation, "min_xy": [2, -1], "max_xy": [4, 1]},
        "traffic_zone": {**citation, "min_xy": [4, -1], "max_xy": [6, 1]},
        "exit_gate": {**citation, "point_xy": [-10, 0]}}
    packet["signal"]["native_actor_id"] = "9"
    path = root / "site.json"
    path.write_text(json.dumps(packet))
    return path


class NativeObservationTests(unittest.TestCase):
    def test_source_plan_body_conflicts_and_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = observation_packet(Path(temp))
            scene, reviewed = plan(path, "stopped_leftmost_clear")
            frame = {"origin": "native_world_snapshot", "time_s": 1.0,
                     "ego": body(-1.75, -5), "signal_state": "Red",
                     "pedestrians": [body(3, 0)], "other_traffic": [body(5, 0)]}
            observed = from_frame(frame, scene, reviewed)
            self.assertAlmostEqual(observed.distance_to_stop_boundary_m, 2.5)
            self.assertEqual(observed.signal, "steady_red_alone")
            self.assertTrue(observed.pedestrian_conflict)
            self.assertTrue(observed.traffic_conflict)
            self.assertFalse(observed.junction_exited)
            frame["ego"] = body(-11, 0)
            frame["signal_state"] = "Green"
            frame["pedestrians"] = []
            frame["other_traffic"] = []
            observed = from_frame(frame, scene, reviewed)
            self.assertTrue(observed.junction_exited)
            self.assertEqual(observed.signal, "other")
            self.assertFalse(observed.pedestrian_conflict)
            with self.assertRaisesRegex(ValueError, "source differs"):
                from_frame(frame, scene, {**reviewed, "source_packet_sha256": "changed"})
            frame["ego"]["body_vertices_xyz_m"] = []
            with self.assertRaisesRegex(ValueError, "ego body vertices"):
                from_frame(frame, scene, reviewed)

    def test_unreviewed_zone_and_live_control(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = observation_packet(root)
            packet = json.loads(path.read_text())
            packet["observation_plan"]["pedestrian_zone"].pop("reviewer")
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "unreviewed conflict"):
                plan(path, "stopped_leftmost_clear")
            path = observation_packet(root)
            class Ego(Actor):
                def __init__(self):
                    super().__init__(1)
                    self.controls = []
                def apply_control(self, control):
                    self.controls.append(control)
            ego = Ego()
            result = run_carla_with_plan(World(), ego, Actor(9), [], [],
                                         packet_path=path, case_suffix="stopped_leftmost_clear",
                                         output_path=root / "trace.jsonl", count=2,
                                         control_factory=lambda **kw: kw)
            rows = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
            self.assertEqual(result["samples"], 2)
            self.assertEqual(len(ego.controls), 2)
            self.assertEqual(rows[0]["position"], {"x": 0.0, "y": 0.0, "z": 0.0})
            self.assertEqual(rows[0]["heading_deg"], 90.0)
            self.assertEqual(rows[0]["speed_mps"], 1.0)


if __name__ == "__main__":
    unittest.main()
