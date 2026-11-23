import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_attempt import run
from saved_entry import CAMERAS
from test_native_packets import Walker, scene, images, snapshot


class Head:
    id = 5
    attributes = {"official_traffic_signal": "true", "governs_pedestrian_route_id": "crossing-1",
                  "signal_shape": "circle", "sole_illuminated": "true"}

    def __init__(self):
        self.state = "Green"
        self.frozen = False

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def freeze(self, value):
        self.frozen = value


class MovingWalker(Walker):
    def __init__(self):
        super().__init__()
        self.control = None

    def get_transform(self):
        return NS(location=NS(x=self.x, y=3.0))

    def apply_control(self, control):
        self.control = control


class World:
    def __init__(self, head, walker):
        self.head, self.walker = head, walker
        self.frame = 0

    def get_actor(self, actor_id):
        return self.head if actor_id == 5 else None

    def tick(self):
        self.frame += 1
        self.walker.x += .8
        return self.frame

    def get_snapshot(self):
        return snapshot(self.frame)


class Recorder:
    def __init__(self, stale=False):
        self.stale = stale
        self.appended = []
        self.closed = False

    def capture(self, frame):
        result = images(frame)
        if self.stale:
            result["overview"].frame -= 1
        return result

    def append(self, captured):
        self.appended.append(captured["overview"].frame)

    def close(self):
        self.closed = True


class NativeAttemptTests(unittest.TestCase):
    def setUp(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.attempt = Path(self.temp.name)
        self.exact = scene()
        self.exact.update(entry_request="entry", target_xy_m=[4, 3], speed_mps=1.2,
                          requested_pedestrian_indication="none", fixed_delta_seconds=.05)
        self.walker = MovingWalker()
        self.head = Head()
        self.world = World(self.head, self.walker)
        self.carla = NS(TrafficLightState=NS(Red="Red"), Vector3D=lambda *v: NS(x=v[0], y=v[1], z=v[2]),
                        WalkerControl=lambda **k: NS(**k))

    def tearDown(self):
        self.temp.cleanup()

    def test_original_tick_loop_writes_five_joined_streams(self):
        recorder = Recorder()
        result = run(self.world, self.carla, self.exact, self.walker, recorder, self.attempt, ticks=3)
        self.assertEqual(result["frame_count"], 3)
        self.assertFalse(result["native_capture_sealed"])
        self.assertTrue(self.head.frozen)
        self.assertEqual(recorder.appended, [1, 2, 3])
        self.assertTrue(recorder.closed)
        self.assertGreater(self.walker.control.speed, 0)
        rows = [json.loads(line) for line in (self.attempt / "camera-frame-joins.jsonl").read_text().splitlines()]
        self.assertEqual([r["frame"] for r in rows], [1, 2, 3])
        self.assertEqual(set(rows[0]["cameras"]), set(CAMERAS))
        trace = [json.loads(line) for line in (self.attempt / "trace.jsonl").read_text().splitlines()]
        self.assertEqual([row["frame"] for row in trace], [1, 2, 3])
        self.assertEqual(trace[0]["position_m"][0], -.8)
        self.assertFalse((self.attempt / "acquisition-provenance.json").exists())

    def test_stale_frame_fails_before_encoding_and_closes(self):
        recorder = Recorder(stale=True)
        with self.assertRaisesRegex(ValueError, "stale or missing"):
            run(self.world, self.carla, self.exact, self.walker, recorder, self.attempt, ticks=3)
        self.assertEqual(recorder.appended, [])
        self.assertTrue(recorder.closed)

    def test_materialized_scene_is_preserved_and_mismatch_rejected(self):
        source = self.attempt / "scene.json"
        source.write_text(json.dumps(self.exact) + "\n")
        (self.attempt / "construction.json").write_text("{}\n")
        before = source.read_bytes()
        other = self.exact.copy()
        other["case_id"] += "_other"
        with self.assertRaisesRegex(ValueError, "materialized Native scene differs"):
            run(self.world, self.carla, other, self.walker, Recorder(), self.attempt, ticks=3)
        result = run(self.world, self.carla, self.exact, self.walker,
                     Recorder(), self.attempt, ticks=3)
        self.assertEqual(result["frame_count"], 3)
        self.assertEqual(source.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "original acquisition already exists"):
            run(self.world, self.carla, other, self.walker, Recorder(), self.attempt, ticks=3)

    def test_review_rejected_before_attempt_mutation(self):
        self.exact["device_inventory_review"]["complete"] = False
        recorder = Recorder()
        with self.assertRaisesRegex(ValueError, "review"):
            run(self.world, self.carla, self.exact, self.walker, recorder, self.attempt, ticks=3)
        self.assertEqual(list(self.attempt.iterdir()), [])
        self.assertTrue(recorder.closed)


if __name__ == "__main__":
    unittest.main()
