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


measure = load("speed_measurements")
control = load("speed_controller")


class Vehicle:
    def __init__(self, speed_mps):
        self.velocity = NS(x=speed_mps, y=0.0, z=0.0)
        self.commands = []

    def get_velocity(self):
        return self.velocity

    def apply_control(self, command):
        self.commands.append(command)


class SpeedTests(unittest.TestCase):
    def fixture(self, root, peak_mph):
        context = {"native_map_id": "TownX", "subject_actor_id": 12,
                   "subject_blueprint_id": "vehicle.sample", "route_source": "native-map-route",
                   "alley_source": "native-map-and-front-video",
                   "access_aisle_source": "native-map-and-side-video"}
        (root / "road_context.json").write_text(json.dumps(context))
        rows = [{"frame": 100 + i, "time_s": 1 + i * .05,
                 "subject_actor_id": 12, "speed_source": "actor.get_velocity",
                 "velocity_mps": [mph * measure.MPH_TO_MPS, 0, 0]}
                for i, mph in enumerate((50, peak_mph))]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "subject_motion.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_strict_80_mph_boundary(self):
        for mph, expected in ((79.99, False), (80.0, False), (80.01, True)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, mph)
                report = measure.analyze(root)
                self.assertEqual(report["sampled_peak_greater_than_80_mph"], expected)
                self.assertAlmostEqual(report["statutory_boundary_mps"], 35.7632)
                self.assertAlmostEqual(report["peak_sample"]["speed_mph"], mph)
                self.assertEqual(report["between_sample_peak"], "unresolved")

    def test_rejects_stale_frame_and_wrong_velocity_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 80.01)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame/time join"):
                measure.analyze(root)
            self.fixture(root, 80.01)
            rows = [json.loads(line) for line in (root / "subject_motion.jsonl").read_text().splitlines()]
            rows[1]["speed_source"] = "requested_target"
            (root / "subject_motion.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "velocity source"):
                measure.analyze(root)

    def test_controller_uses_native_velocity_and_applies_controls(self):
        factory = lambda **values: NS(**values)
        controller = control.SpeedController(80, factory)
        vehicle = Vehicle(10)
        command = controller.step(vehicle, distance_to_route_end_m=500)
        self.assertGreater(command["throttle"], 0)
        self.assertEqual(vehicle.commands[-1].brake, 0)
        vehicle.velocity.x = 40
        command = controller.step(vehicle, distance_to_route_end_m=500)
        self.assertGreater(command["brake"], 0)
        vehicle.velocity.x = 20
        command = controller.step(vehicle, distance_to_route_end_m=10)
        self.assertEqual(command["brake"], 1.0)
        self.assertEqual(len(vehicle.commands), 3)


if __name__ == "__main__":
    unittest.main()
