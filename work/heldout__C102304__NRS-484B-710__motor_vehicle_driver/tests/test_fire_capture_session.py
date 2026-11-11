import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


folder = Path(__file__).resolve().parents[1]
runtime = folder.parents[1] / "runtime"
sys.path.insert(0, str(runtime))


def load(name):
    spec = importlib.util.spec_from_file_location(name, folder / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


session_module = load("fire_capture_session")
finalizer = load("fire_finalizer")


def point(x, y, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


class Actor:
    def __init__(self, actor_id, x, direction):
        self.id, self.x, self.direction = actor_id, x, direction
        self.bounding_box = SimpleNamespace(get_world_vertices=self.vertices)

    def vertices(self, _):
        return [point(self.x + dx, dy, z) for dx in (-2, 2)
                for dy in (-1, 1) for z in (0, 1)]

    def get_transform(self):
        return SimpleNamespace(location=point(self.x, 0),
                               get_forward_vector=lambda: point(self.direction, 0))

    def get_velocity(self):
        return point(self.direction * 6, 0)

    def get_control(self):
        return SimpleNamespace(hand_brake=False)


class FakePipeline:
    def __init__(self, output, ego):
        self.output, self.ego = output, ego
        self.trace = (output / "trace.jsonl").open("x")

    def capture(self, frame, time_s):
        row = {"frame": frame, "time_s": time_s,
               "position_m": [self.ego.x, 0, 0]}
        self.trace.write(json.dumps(row) + "\n")
        self.trace.flush()
        return row

    def close(self):
        self.trace.close()


class FireCaptureSessionTests(unittest.TestCase):
    def test_original_tick_join_reaches_saved_measurement_both_directions(self):
        context = {"alarm_response_source": "authored dispatch premise",
                   "apparatus_answered_alarm": True,
                   "subject_authorized_emergency": False,
                   "subject_official_business": False}
        for direction in (1, -1):
            with self.subTest(direction=direction), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                config = {"law_id": "NRS-484B-710", "selected_case_id": "fire-at-500",
                          "fire_branch": "traveling_follow"}
                (output / "config.json").write_text(json.dumps(config))
                ego = Actor(1, 0, direction)
                apparatus = Actor(2, direction * (4 + 500 / 3.280839895013123), direction)
                pipeline = FakePipeline(output, ego)
                try:
                    with session_module.FireCaptureSession(output, pipeline, ego, apparatus, context) as session:
                        for frame in (10, 11):
                            session.capture(frame, frame / 20,
                                            warning_lamp_readback=True,
                                            siren_readback=True)
                            ego.x += direction
                            apparatus.x += direction
                finally:
                    pipeline.close()
                report = finalizer.analyze(output)
                self.assertEqual(report["measurements"]["fire_boundary_observation"]
                                 ["value"]["active_frame_count"], 2)

    def test_missing_readback_rejected_before_pipeline_capture(self):
        context = {"alarm_response_source": "authored dispatch premise",
                   "apparatus_answered_alarm": True,
                   "subject_authorized_emergency": False,
                   "subject_official_business": False}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            ego, apparatus = Actor(1, 0, 1), Actor(2, 150, 1)
            pipeline = FakePipeline(output, ego)
            try:
                with session_module.FireCaptureSession(output, pipeline, ego, apparatus, context) as session:
                    with self.assertRaisesRegex(ValueError, "Warning lamp requires"):
                        session.capture(10, .5, warning_lamp_readback=None,
                                        siren_readback=True)
                self.assertEqual((output / "trace.jsonl").read_text(), "")
            finally:
                pipeline.close()


if __name__ == "__main__":
    unittest.main()
