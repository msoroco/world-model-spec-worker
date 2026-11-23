import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stand_route import make
from taxi_cameras import NAMES
from taxi_capture_ticks import capture_ticks
from taxi_native_motion import route_points
from test_taxi_native_motion import FakeCarla


class FakeWorld:
    def __init__(self, points, mismatch=False):
        self.points = points
        self.frame = 0
        self.mismatch = mismatch

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        frame = self.frame + (1 if self.mismatch else 0)
        return SimpleNamespace(frame=frame,
                               timestamp=SimpleNamespace(elapsed_seconds=self.frame / 20))


class FakeActor:
    def __init__(self, world):
        self.world = world

    def get_transform(self):
        x, y = self.world.points[min(self.world.frame, len(self.world.points) - 1)]
        return SimpleNamespace(location=SimpleNamespace(x=x, y=y),
                               rotation=SimpleNamespace(yaw=0))

    def get_velocity(self):
        return SimpleNamespace(x=0, y=0, z=0)

    def apply_control(self, control):
        self.last_control = control


class FakeTrace:
    def __init__(self, root, world):
        self.root = root
        self.world = world
        self.closed = False
        self.completed = None

    def record(self):
        snapshot = self.world.get_snapshot()
        return {"frame": snapshot.frame, "time_s": snapshot.timestamp.elapsed_seconds}

    def close(self, *, completed):
        self.closed = True
        self.completed = completed
        return {"sealed": True} if completed else None


class TickLoopTest(unittest.TestCase):
    def test_four_view_frame_join_and_completed_trace_seal(self):
        layout = make("near_stand")
        points = route_points(layout)
        world = FakeWorld(points)
        actor = FakeActor(world)
        frames = []
        cameras = SimpleNamespace(queues=dict.fromkeys(NAMES), append=lambda frame: frames.append(frame))
        pipeline = SimpleNamespace(capture=lambda frame, time: frames.append(frame))
        frame_map = SimpleNamespace(append=lambda frame, time: frames.append(frame))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            trace = FakeTrace(root, world)
            count = len(points) + 2
            result = capture_ticks(world, actor, FakeCarla, layout, root,
                                   pipeline, cameras, frame_map, trace,
                                   duration_s=count / 20)
            self.assertTrue(result["maneuver_completed"])
            self.assertEqual(result["trace_seal"], {"sealed": True})
            self.assertEqual(len(result["frames"]), count)
            self.assertEqual(len(frames), count * 3)
            self.assertTrue(trace.closed and trace.completed)

    def test_world_frame_mismatch_aborts_unsealed_trace(self):
        layout = make("near_stand")
        world = FakeWorld(route_points(layout), mismatch=True)
        actor = FakeActor(world)
        cameras = SimpleNamespace(queues=dict.fromkeys(NAMES), append=lambda frame: None)
        pipeline = SimpleNamespace(capture=lambda frame, time: None)
        frame_map = SimpleNamespace(append=lambda frame, time: None)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            trace = FakeTrace(root, world)
            with self.assertRaisesRegex(RuntimeError, "frame mismatch"):
                capture_ticks(world, actor, FakeCarla, layout, root,
                              pipeline, cameras, frame_map, trace,
                              duration_s=1)
            self.assertTrue(trace.closed)
            self.assertFalse(trace.completed)


if __name__ == "__main__":
    unittest.main()
