import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from carla_adapter import CarlaNativeAdapter
from native_capture import capture
from saved_delivery import join
from test_native_capture import SCENE, packet, png


class Actor:
    def __init__(self, actor_id, xy):
        self.id = actor_id
        self.xy = xy

    def get_transform(self):
        point = type("Point", (), {"x": self.xy[0], "y": self.xy[1]})()
        return type("Transform", (), {"location": point})()

    def get_control(self):
        return type("Control", (), {"brake": 1.0})()


class World:
    def __init__(self):
        self.frame = 999
        self.name = "SourceTown"
        self.synchronous_mode = True
        self.fixed_delta_seconds = .05

    def get_map(self):
        return type("Map", (), {"name": self.name})()

    def get_settings(self):
        return self

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        timestamp = type("Time", (), {"elapsed_seconds": 100 + (self.frame - 1000) / 20})()
        return type("Snapshot", (), {"frame": self.frame, "timestamp": timestamp})()


class CarlaAdapterTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work/c111610-carla-adapter-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.site = self.root / "site.json"
        self.site.write_text(json.dumps(packet()) + "\n")
        self.exception = self.root / "exception.json"
        self.exception.write_text(json.dumps({
            "case_id": json.loads(SCENE.read_text())["case_id"],
            "status": "none_identified", "source_refs": ["review/exception-source.json"]}) + "\n")
        self.world = World()
        self.ego = Actor(101, [0, -2])
        self.pedestrian = Actor(202, [1, 2])
        image = png()
        self.readers = {name: lambda frame, body=image: {"frame": frame, "png_bytes": body}
                        for name in ("overview", "approach", "reference_corner", "driver_reference")}

    def adapter(self, **kwargs):
        return CarlaNativeAdapter(self.world, self.ego, self.pedestrian,
                                  self.readers, self.site, "reviewed Native source fixture",
                                  **kwargs)

    def test_exact_capture_and_saved_delivery_join(self):
        adapter = self.adapter()
        dims = {name: (2, 2) for name in self.readers}
        attempt = self.root / "attempt"
        index = capture(adapter, SCENE, self.site, self.exception, attempt,
                        dimensions=dims)
        self.assertEqual(index["native_source_attestation"]["site_sha256"],
                         hashlib.sha256(self.site.read_bytes()).hexdigest())
        receipt = join(attempt, SCENE, self.root / "delivery.json", dimensions=dims)
        self.assertEqual(receipt["decoded_view_frames"], 2400)
        self.assertFalse(receipt["physical_source_verified"])

    def test_rejects_world_source_camera_and_actor_mismatch(self):
        self.world.synchronous_mode = False
        with self.assertRaisesRegex(ValueError, "synchronous"):
            self.adapter()
        self.world.synchronous_mode = True
        adapter = self.adapter()
        self.world.name = "DifferentTown"
        with self.assertRaisesRegex(ValueError, "map changed"):
            adapter.tick()
        self.world.name = "SourceTown"
        self.site.write_text(self.site.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "site source changed"):
            adapter.tick()
        self.site.write_text(self.site.read_text()[:-1])
        self.readers["approach"] = lambda frame: {"frame": frame + 1,
                                                  "png_bytes": png()}
        with self.assertRaisesRegex(ValueError, "camera frame"):
            self.adapter().tick()
        self.pedestrian.id = self.ego.id
        with self.assertRaisesRegex(ValueError, "separate original"):
            self.adapter()
