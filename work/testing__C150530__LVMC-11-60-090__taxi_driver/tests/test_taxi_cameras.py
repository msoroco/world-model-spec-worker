import io
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stand_route import make
from taxi_cameras import CameraCapture, NAMES, RATE_HZ, SIZES, poses
from test_taxi_native_motion import FakeCarla


class FakeSensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def emit(self, frame):
        self.callback(SimpleNamespace(frame=frame, raw_data=b"synthetic pixels"))

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class FakeProcess:
    def __init__(self, code=0):
        self.stdin = io.BytesIO()
        self.code = code

    def wait(self, timeout):
        return self.code


class FakeWorld:
    def __init__(self):
        self.sensors = []
        self.attachments = []
        self.blueprint = SimpleNamespace(set_attribute=lambda key, value: None)

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: self.blueprint if name == "sensor.camera.rgb" else None)

    def spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = FakeSensor()
        self.sensors.append(sensor)
        self.attachments.append(attach_to)
        return sensor


class CameraTest(unittest.TestCase):
    def test_both_case_poses_cover_distinct_stand_and_first_turn(self):
        for case in ("near_stand", "far_stand"):
            with self.subTest(case=case):
                plan = poses(make(case))
                self.assertEqual(tuple(plan), NAMES)
                self.assertEqual(plan["overview"]["xyz"][2], 80)
                self.assertLess(plan["approach"]["xyz"][0], make(case)["stand"]["center"][0])
                self.assertTrue(plan["driver_reference"]["attached"])
                self.assertTrue(all(math.isfinite(value) for pose in plan.values()
                                    for value in (*pose["xyz"], pose["yaw"], pose["pitch"])))

    def test_four_sensors_encode_same_original_frame_and_close(self):
        world = FakeWorld()
        processes = []
        commands = []

        def popen(command, **kwargs):
            commands.append(command)
            process = FakeProcess()
            processes.append(process)
            return process

        with tempfile.TemporaryDirectory() as temp:
            capture = CameraCapture(world, object(), make("near_stand"), Path(temp),
                                    FakeCarla, popen=popen)
            self.assertEqual(len(world.sensors), 4)
            self.assertEqual([command[command.index("-framerate") + 1] for command in commands],
                             [str(RATE_HZ)] * 4)
            self.assertEqual([command[command.index("-video_size") + 1] for command in commands],
                             [f"{w}x{h}" for w, h in SIZES])
            self.assertEqual(sum(item is not None for item in world.attachments), 1)
            for sensor in world.sensors:
                sensor.emit(42)
            capture.append(42)
            capture.close()
            self.assertEqual(capture.exit_codes, dict.fromkeys(NAMES, 0))
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
            self.assertTrue(all(process.stdin.closed for process in processes))

    def test_mismatched_camera_frame_is_rejected(self):
        world = FakeWorld()
        with tempfile.TemporaryDirectory() as temp:
            capture = CameraCapture(world, object(), make("near_stand"), Path(temp),
                                    FakeCarla, popen=lambda *a, **k: FakeProcess())
            for index, sensor in enumerate(world.sensors):
                sensor.emit(7 if index != 2 else 8)
            with self.assertRaisesRegex(RuntimeError, "frame mismatch"):
                capture.append(7)
            capture.close()

    def test_failed_encoder_exit_is_retained_and_raises(self):
        world = FakeWorld()
        codes = iter((0, 1, 0, 0))
        with tempfile.TemporaryDirectory() as temp:
            capture = CameraCapture(world, object(), make("near_stand"), Path(temp),
                                    FakeCarla, popen=lambda *a, **k: FakeProcess(next(codes)))
            with self.assertRaisesRegex(RuntimeError, "encoder failed"):
                capture.close()
            self.assertEqual(capture.exit_codes["approach"], 1)


if __name__ == "__main__":
    unittest.main()
