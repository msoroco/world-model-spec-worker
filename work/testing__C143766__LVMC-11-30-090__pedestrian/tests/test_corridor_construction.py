import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_corridor_diagnostics import body, build
from corridor_construction import compare_authored_routes, make_scene, measure_original, request_next_target, validate_scene
from native_driver import apply_walker_request
from corridor_map import map_sha256, verify_candidate_map


class CorridorTests(unittest.TestCase):
    def test_three_exact_routes_and_synthetic_body_bands(self):
        proof = build(ROOT)
        self.assertEqual(proof["map"]["map_sha256"], map_sha256())
        self.assertEqual(len(proof["cases"]), 3)
        self.assertEqual(len(proof["comparisons"]), 2)
        for band in ("roadway", "shoulder", "sidewalk"):
            item = proof["cases"][next(k for k in proof["cases"] if k.endswith("__"+band+"_walk"))]
            self.assertEqual(item["measurement"]["band_overlap_frame_counts"][band], 3)
            self.assertEqual(item["measurement"]["legal_judgment"], "unresolved")
            self.assertEqual(item["first_walker_request"]["speed_mps"], 1.2)

    def test_gap_or_overlap_between_roadway_shoulder_sidewalk_rejected(self):
        scene = make_scene("test", "roadway")
        for edge in (3.1, 2.9):
            changed = copy.deepcopy(scene)
            changed["bounds_xy_m"]["shoulder"][1] = edge
            with self.assertRaisesRegex(ValueError, "overlap or gap"):
                validate_scene(changed)

    def test_body_crossing_roadway_shoulder_boundary_rejected(self):
        scene = make_scene("test", "roadway")
        scene["pedestrian_route_xy_m"][1][1] = 2.9
        with self.assertRaisesRegex(ValueError, "body leaves"):
            validate_scene(scene)

    def test_original_frames_and_full_body_required(self):
        scene = make_scene("test", "roadway")
        frames = [{"frame": i, "body_xy_m": body(2+i*13, 1.5)} for i in range(3)]
        self.assertEqual(measure_original(scene, frames)["frames"], 3)
        frames[1]["frame"] = 4
        with self.assertRaisesRegex(ValueError, "missing or stale"):
            measure_original(scene, frames)
        frames[1]["frame"] = 1
        frames[1]["body_xy_m"] = [[1, 1]]
        with self.assertRaisesRegex(ValueError, "full-body"):
            measure_original(scene, frames)

    def test_standing_still_is_not_walking_along_corridor(self):
        scene = make_scene("test", "roadway")
        frames = [{"frame": i, "body_xy_m": body(2, 1.5)} for i in range(3)]
        with self.assertRaisesRegex(ValueError, "did not progress"):
            measure_original(scene, frames)

    def test_comparison_rejects_undeclared_or_extra_changes(self):
        first = make_scene("first", "roadway")
        second = make_scene("second", "sidewalk")
        self.assertTrue(compare_authored_routes(first, second, True)["fixed_corridor_and_longitudinal_route"])
        with self.assertRaisesRegex(ValueError, "not declared"):
            compare_authored_routes(first, second, False)
        changed = copy.deepcopy(second)
        changed["pedestrian_route_xy_m"][1][0] = 16
        with self.assertRaisesRegex(ValueError, "longitudinal"):
            compare_authored_routes(first, changed, True)

    def test_walker_request_advances_and_stops(self):
        scene = make_scene("test", "sidewalk")
        self.assertEqual(request_next_target(scene, 15, 5)["target_index"], 2)
        self.assertEqual(request_next_target(scene, 28, 5, 2)["speed_mps"], 0)

    def test_candidate_opendrive_lane_types_and_source_hash(self):
        from tempfile import TemporaryDirectory
        proof = build(ROOT)
        self.assertEqual(proof["map"]["lane_types"],
                         ["driving", "shoulder", "sidewalk", "border", "biking"])
        source = (ROOT / "candidate-corridor.xodr").read_bytes()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.xodr"
            path.write_bytes(source.replace(b'type="sidewalk"', b'type="driving"'))
            with self.assertRaisesRegex(ValueError, "source bytes changed"):
                verify_candidate_map(path)

    def test_native_walker_control_request_uses_original_pose(self):
        class Carla:
            @staticmethod
            def Vector3D(**kwargs): return kwargs
            @staticmethod
            def WalkerControl(**kwargs): return kwargs
        class Actor:
            def __init__(self, x, y):
                self.pose = type("Pose", (), {"location": type("Point", (), {"x": x, "y": y})()})()
                self.control = None
            def get_transform(self): return self.pose
            def apply_control(self, control): self.control = control
        scene = make_scene("test", "roadway")
        actor = Actor(2, 1.5)
        request = apply_walker_request(actor, Carla, scene)
        self.assertEqual(request["target_index"], 1)
        self.assertEqual(actor.control["direction"]["x"], 1)
        self.assertEqual(actor.control["speed"], 1.2)
        actor.pose.location.x = float("nan")
        with self.assertRaisesRegex(ValueError, "original walker pose"):
            apply_walker_request(actor, Carla, scene)


if __name__ == "__main__":
    unittest.main()
