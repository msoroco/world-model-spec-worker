import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load("posted_speed_measurements")
construction = load("sign_construction")
control = load("speed_controller")


class FakeActors(list):
    def filter(self, pattern):
        assert pattern == "traffic.speed_limit*"
        return self


class PostedSpeedTests(unittest.TestCase):
    def fixture(self, root, speed_mph):
        context = {"native_map_id": "TownX", "subject_actor_id": 10,
                   "governed_road_id": 4, "sign_actor_id": 25,
                   "sign_landmark_id": "OpenDRIVE-25", "authority_source": "reviewed-posting-source",
                   "face_video_source": "front-original", "governance_source": "native-trigger-and-landmark",
                   "narrow_road_source": "native-road-width-and-camera",
                   "posted_limit_value": 25, "posted_unit": "mph",
                   "zone_start_s_m": 100, "zone_end_s_m": 300}
        (root / "sign_context.json").write_text(json.dumps(context))
        rows = []
        for i, (road, s, mph) in enumerate(((9, 50, 80), (4, 110, speed_mph), (4, 120, speed_mph))):
            rows.append({"frame": 100+i, "time_s": 1+i*.05,
                         "subject_actor_id": 10, "speed_source": "actor.get_velocity",
                         "road_id": road, "road_s_m": s,
                         "velocity_mps": [mph * .44704, 0, 0]})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "subject_motion.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_strict_posted_boundary_uses_only_governed_portion(self):
        for mph, above in ((24.99, False), (25.0, False), (25.01, True)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, mph)
                result = measure.analyze(root)
                self.assertEqual(result["sampled_peak_greater_than_posted"], above)
                self.assertAlmostEqual(result["peak_in_zone"]["measured_speed_mph"], mph)
                self.assertFalse(result["samples"][0]["in_signed_zone"])

    def test_missing_authority_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 25.01)
            context = json.loads((root / "sign_context.json").read_text())
            context["authority_source"] = ""
            (root / "sign_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "posted-speed context"):
                measure.analyze(root)
            self.fixture(root, 25.01)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)

    def test_native_sign_trigger_and_value_match(self):
        def sign(value, within):
            return NS(type_id=f"traffic.speed_limit.{value}",
                      trigger_volume=NS(contains=lambda point, transform: within),
                      get_transform=lambda: "sign-transform")
        selected = sign(25, True)
        world = NS(get_actors=lambda: FakeActors([sign(30, True), sign(25, False), selected]))
        approach = NS(transform=NS(location="approach-point"))
        self.assertIs(construction.find_governing_speed_sign(world, approach, 25), selected)
        with self.assertRaisesRegex(ValueError, "found 0"):
            construction.find_governing_speed_sign(world, approach, 35)

    def test_controller_applies_bounded_native_control_and_brakes_at_end(self):
        applied = []
        vehicle = NS(get_velocity=lambda: NS(x=0.0, y=0.0, z=0.0),
                     apply_control=applied.append)
        controller = control.PostedSpeedController(25, lambda **kwargs: kwargs)
        result = controller.step(vehicle, remaining_route_m=100)
        self.assertGreater(result["throttle"], 0)
        self.assertEqual(applied[-1]["brake"], 0)
        controller.step(vehicle, remaining_route_m=1)
        self.assertEqual(applied[-1]["brake"], 1)


if __name__ == "__main__":
    unittest.main()
