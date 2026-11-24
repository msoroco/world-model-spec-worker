import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import capture
from test_saved_instruction import SITE, SITE_SHA, CASE


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class Transform:
    def __init__(self, x):
        self.location = Vector(x=x)

    def get_forward_vector(self):
        return Vector(x=1.0)


class Bike:
    id = 22
    type_id = "vehicle.bicycle"
    bounding_box = type("BoundingBox", (), {"extent": Vector(x=0.5)})()

    def __init__(self, world):
        self.world = world
        self.braked = False

    def get_transform(self):
        i = self.world.frame - 100
        return Transform(-10.5 + 20 * i / 899)

    def get_velocity(self):
        return Vector(x=3.0)

    def set_target_velocity(self, value):
        self.braked = value.x == 0 and value.y == 0 and value.z == 0


class World:
    frame = 99
    bad_frame = None

    def tick(self):
        self.frame += 1
        return self.frame + (1 if self.frame == self.bad_frame else 0)

    def get_snapshot(self):
        timestamp = type("Timestamp", (), {"elapsed_seconds": self.frame * 0.05})()
        return type("Snapshot", (), {"frame": self.frame, "timestamp": timestamp})()


def officer_reader(_snapshot, _bike):
    return {"actor_id": None, "authority_source": None,
            "recipient_id": None, "command": "none"}


class TestNativeCapture(unittest.TestCase):
    def test_original_world_readback_to_saved_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = World()
            bike = Bike(world)
            device = type("Device", (), {"id": 10})()
            path = Path(tmp) / "native-trace.json"
            value = capture(world, bike, device, CASE, SITE, SITE_SHA,
                            lambda _device, _snapshot: "red", officer_reader, path)
            self.assertEqual(value["frame_count"], 900)
            self.assertIsNotNone(value["crossing_frame"])
            self.assertTrue(path.exists())
            self.assertTrue(bike.braked)

    def test_frame_and_device_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = World()
            world.bad_frame = 150
            bike = Bike(world)
            device = type("Device", (), {"id": 10})()
            path = Path(tmp) / "bad-frame.json"
            with self.assertRaisesRegex(ValueError, "tick and snapshot"):
                capture(world, bike, device, CASE, SITE, SITE_SHA,
                        lambda _device, _snapshot: "red", officer_reader, path)
            self.assertFalse(path.exists())
            self.assertTrue(bike.braked)
            world = World()
            bike = Bike(world)
            with self.assertRaisesRegex(ValueError, "instruction differs"):
                capture(world, bike, device, CASE, SITE, SITE_SHA,
                        lambda _device, _snapshot: "green", officer_reader,
                        Path(tmp) / "wrong-device.json")
            self.assertTrue(bike.braked)


if __name__ == "__main__":
    unittest.main()
