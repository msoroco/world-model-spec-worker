"""Exercise synchronized four-camera and world-tick Native call shapes."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_cameras import CAMERAS, CameraCapture
from parking_scene import build
from parking_tick_capture import capture_ticks
from test_parking_native_capture import Point
from test_source_review import fixture


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class Encoder:
    def __init__(self):
        self.data = []
        self.stdin = SimpleNamespace(closed=False, write=self.data.append, close=self.close)

    def close(self):
        self.stdin.closed = True

    def wait(self, timeout):
        return 0


class Vehicle:
    bounding_box = SimpleNamespace(location=Point(0, 0), extent=Point(2.25, 1, 1))

    def __init__(self):
        self.control = SimpleNamespace(throttle=0, steer=0, brake=1)

    def get_transform(self):
        return SimpleNamespace(location=Point(0, 2.5),
                               get_forward_vector=lambda: Point(1, 0),
                               transform=lambda point: Point(point.x, point.y + 2.5))

    def get_velocity(self):
        return Point(0, 0)

    def get_control(self):
        return self.control

    def apply_control(self, control):
        self.control = control


CARLA = SimpleNamespace(Location=lambda **k: Point(**k),
                        Rotation=lambda **k: SimpleNamespace(**k),
                        Transform=lambda loc, rot: (loc, rot),
                        VehicleControl=lambda **k: SimpleNamespace(**k))


class TickCaptureTests(unittest.TestCase):
    def test_four_camera_spawn_encode_join_and_cleanup(self):
        sensors, encoders, commands, attached = [], [], [], []

        class World:
            def get_blueprint_library(self):
                return SimpleNamespace(find=lambda name: SimpleNamespace(set_attribute=lambda *a: None))

            def spawn_actor(self, blueprint, transform, attach_to=None):
                sensor = Sensor()
                sensors.append(sensor)
                attached.append(attach_to)
                return sensor

        def popen(command, **kwargs):
            commands.append(command)
            encoder = Encoder()
            encoders.append(encoder)
            return encoder

        with TemporaryDirectory() as source, TemporaryDirectory() as output:
            packet, _ = fixture(source)
            scene = build(packet, source, "park_parallel_lawful")
            vehicle = Vehicle()
            cameras = CameraCapture(World(), vehicle, scene, output, CARLA, popen=popen)
            self.assertEqual(attached, [None, None, None, vehicle])
            self.assertEqual([Path(command[-1]).stem for command in commands], list(CAMERAS))
            self.assertIn("1920x1080", commands[0])
            self.assertTrue(all("1280x720" in command for command in commands[1:]))
            for sensor in sensors:
                sensor.callback(SimpleNamespace(frame=42, raw_data=b"frame"))
            cameras.append(42)
            self.assertTrue(all(encoder.data == [b"frame"] for encoder in encoders))
            cameras.close()
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in sensors))

    def test_tick_capture_original_join_and_world_mismatch(self):
        class World:
            def __init__(self):
                self.frame = 0
                self.bad = False

            def tick(self):
                self.frame += 1
                return self.frame

            def get_snapshot(self):
                return SimpleNamespace(frame=self.frame + int(self.bad),
                                       timestamp=SimpleNamespace(elapsed_seconds=self.frame * .05))

        class Receiver:
            def __init__(self):
                self.calls = []

            def capture(self, *args):
                self.calls.append(args)

            def append(self, *args):
                self.calls.append(args)

        scratch = ROOT.parents[1] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory() as source, TemporaryDirectory(dir=scratch) as output:
            packet, _ = fixture(source)
            scene = build(packet, source, "park_parallel_lawful")
            world, vehicle = World(), Vehicle()
            pipeline, cameras, frame_map = Receiver(), Receiver(), Receiver()
            result = capture_ticks(world, vehicle, scene, output, CARLA,
                                   pipeline, cameras, frame_map, sample_count=2)
            self.assertEqual(result["frames"], [1, 2])
            self.assertEqual(pipeline.calls, [(1, .05), (2, .1)])
            self.assertEqual(cameras.calls, [(1,), (2,)])
            self.assertEqual(frame_map.calls, [(1, .05), (2, .1)])
            rows = [json.loads(line) for line in (Path(output) / "parking-history.jsonl").read_text().splitlines()]
            camera_rows = [json.loads(line) for line in (Path(output) / "camera-frame-map.jsonl").read_text().splitlines()]
            self.assertEqual([row["frame"] for row in rows], [1, 2])
            self.assertEqual([row["camera_names"] for row in camera_rows], [list(CAMERAS)] * 2)
            self.assertFalse(result["physical_acceptance_claimed"])
            with self.assertRaisesRegex(FileExistsError, "File exists"):
                capture_ticks(world, vehicle, scene, output, CARLA,
                              pipeline, cameras, frame_map, sample_count=1)
        with TemporaryDirectory(dir=scratch) as output:
            world = World()
            world.bad = True
            with self.assertRaisesRegex(RuntimeError, "world frame mismatch"):
                capture_ticks(world, Vehicle(), scene, output, CARLA,
                              Receiver(), Receiver(), Receiver(), sample_count=1)

    def test_tick_capture_rejects_skipped_frame_and_backward_time(self):
        class World:
            def __init__(self, *, skip=False, backward=False):
                self.frame = 0
                self.skip = skip
                self.backward = backward

            def tick(self):
                self.frame += 2 if self.skip and self.frame else 1
                return self.frame

            def get_snapshot(self):
                time_s = .05 if self.backward else self.frame * .05
                return SimpleNamespace(frame=self.frame,
                                       timestamp=SimpleNamespace(elapsed_seconds=time_s))

        class Receiver:
            def capture(self, *args):
                pass

            def append(self, *args):
                pass

        scratch = ROOT.parents[1] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory() as source:
            packet, _ = fixture(source)
            scene = build(packet, source, "park_parallel_lawful")
            for world, error in ((World(skip=True), "frame sequence is not contiguous"),
                                 (World(backward=True), "timestamp is not finite and increasing")):
                with self.subTest(error=error), TemporaryDirectory(dir=scratch) as output:
                    with self.assertRaisesRegex(RuntimeError, error):
                        capture_ticks(world, Vehicle(), scene, output, CARLA,
                                      Receiver(), Receiver(), Receiver(), sample_count=2)
                    rows = (Path(output) / "parking-history.jsonl").read_text().splitlines()
                    self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
