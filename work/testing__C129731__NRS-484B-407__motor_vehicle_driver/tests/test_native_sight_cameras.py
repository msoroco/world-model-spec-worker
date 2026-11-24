import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_sight_cameras import NativeSightCameras, SPECS


class Sensor:
    def __init__(self):
        self.receive = None
        self.stopped = self.destroyed = False

    def listen(self, callback):
        self.receive = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class Process:
    def __init__(self, args, stdin, stderr):
        self.stdin = Obj(closed=False, write=lambda data: len(data),
                         close=lambda: setattr(self.stdin, "closed", True))

    def wait(self, timeout):
        return 0


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sensors = []

        def spawn(bp, transform):
            sensor = Sensor()
            self.sensors.append(sensor)
            return sensor

        self.world = Obj(get_blueprint_library=lambda: Obj(find=lambda name: Obj(
            set_attribute=lambda key, value: None)), spawn_actor=spawn)
        self.carla = Obj(Location=lambda **kw: kw, Rotation=lambda **kw: kw,
                         Transform=lambda location, rotation: (location, rotation))
        self.site = {"camera_mounts": {name: dict(x=0, y=0, z=5, pitch=0,
                                                   yaw=0, roll=0, fov=75)
                                       for name, _, _ in SPECS}}

    def test_exact_four_reviewed_mounts_and_frame_join(self):
        cameras = NativeSightCameras(self.world, self.site, Path(self.tmp.name),
                                     self.carla, Process)
        self.assertEqual(len(self.sensors), 4)
        self.sensors[0].receive(Obj(frame=8, raw_data=b"bad"))
        with self.assertRaisesRegex(RuntimeError, "raw frame size mismatch"):
            cameras.append(8)
        cameras.close()
        self.assertTrue(all(sensor.stopped and sensor.destroyed
                            for sensor in self.sensors))

    def test_missing_or_nonfinite_mount_rejected_before_spawn(self):
        del self.site["camera_mounts"]["approach"]
        with self.assertRaisesRegex(ValueError, "four reviewed camera mounts"):
            NativeSightCameras(self.world, self.site, Path(self.tmp.name),
                               self.carla, Process)
        self.assertFalse(self.sensors)
        self.site["camera_mounts"]["approach"] = dict(x=0, y=0, z=5,
            pitch=0, yaw=0, roll=0, fov=float("nan"))
        with self.assertRaisesRegex(ValueError, "incomplete reviewed camera mount"):
            NativeSightCameras(self.world, self.site, Path(self.tmp.name),
                               self.carla, Process)


if __name__ == "__main__":
    unittest.main()
