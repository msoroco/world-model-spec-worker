import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carla_readback import CameraFrames, device_reader
from native_observation import CAMERAS, capture_observation
import test_site_geometry


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        source = test_site_geometry.CrossingSiteTests("test_unmarked_and_marked_comparison")
        source.setUp()
        self.addCleanup(source.tmp.cleanup)
        self.packet = source.packet
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dims = {name: (8, 6) for name in CAMERAS}

    def test_exact_camera_and_device_capture(self):
        buffer = CameraFrames(self.dims)
        ids = [d["device_id"] for d in self.packet["devices"]]

        class Actor:
            def __init__(self, actor_id):
                self.id = actor_id
            def get_state(self):
                return "Green"

        read_device = device_reader(self.packet,
                                    {ids[0]: Actor(11), ids[1]: Actor(12)},
                                    lambda device_id, actor: actor.id == 11)

        class World:
            frame = 0
            def tick(self):
                self.frame += 1
                for name in CAMERAS:
                    image = type("Image", (), {"frame": self.frame, "width": 8,
                        "height": 6, "raw_data": bytes([12, 34, 56, 255]) * 48})()
                    buffer.callback(name)(image)
                return self.frame
            def get_snapshot(self):
                return type("Snapshot", (), {"frame": self.frame,
                    "timestamp": type("Timestamp", (), {"elapsed_seconds": self.frame * .05})()})()

        class Walker:
            def __init__(self, world):
                self.world = world
            def get_location(self):
                return type("Location", (), {"x": 50,
                    "y": [-10, -5, 0, 5, 10][self.world.frame - 1], "z": 0})()

        world = World()
        receipt = capture_observation(world, Walker(world), self.packet, "case-one",
                  Path(self.tmp.name) / "observation.json", read_device, ticks=5,
                  camera_readers=buffer.readers(), camera_dimensions=self.dims)
        self.assertTrue(receipt["camera_capture_complete"])
        self.assertEqual(receipt["frame_count"], 5)
        self.assertTrue(all(not buffer.pending[name] for name in CAMERAS))

    def test_rejects_wrong_frame_and_bad_bgra(self):
        buffer = CameraFrames(self.dims)
        image = type("Image", (), {"frame": 7, "width": 8, "height": 6,
                                   "raw_data": bytes(8 * 6 * 4)})()
        buffer.callback("overview")(image)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            buffer.reader("overview")(8)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            buffer.callback("overview")(image)
        image.raw_data = b"short"
        with self.assertRaisesRegex(ValueError, "byte count"):
            buffer.callback("approach")(image)

    def test_rejects_device_identity_and_unproved_operation(self):
        ids = [d["device_id"] for d in self.packet["devices"]]
        actor = type("Actor", (), {"id": 11, "get_state": lambda self: "Green"})()
        with self.assertRaisesRegex(ValueError, "distinct"):
            device_reader(self.packet, {ids[0]: actor, ids[1]: actor}, lambda *_: True)
        other = type("Actor", (), {"id": 12, "get_state": lambda self: "Green"})()
        read = device_reader(self.packet, {ids[0]: actor, ids[1]: other}, lambda *_: None)
        with self.assertRaisesRegex(ValueError, "operation unavailable"):
            read(ids[0])


if __name__ == "__main__":
    unittest.main()
