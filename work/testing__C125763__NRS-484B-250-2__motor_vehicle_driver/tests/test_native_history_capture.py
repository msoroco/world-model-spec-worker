import hashlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from native_history_capture import capture, audit_media, CAMERAS
from crossing_timing import measure
from saved_finalizer import finalize


class Vertex:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Box:
    def get_world_vertices(self, transform):
        x, y = transform
        return [Vertex(x + dx, y + dy, z) for dx in (-.4, .4)
                for dy in (-.4, .4) for z in (-.5, .5)]


class Actor:
    bounding_box = Box()

    def __init__(self, world, actor_id, positions):
        self.world, self.id, self.positions = world, actor_id, positions

    def get_transform(self):
        return self.positions[self.world.index], 0


class Map:
    def to_opendrive(self):
        return "<OpenDRIVE/>\n"


class World:
    def __init__(self):
        self.index = -1
        self.map = Map()
        self.settings = type("Settings", (), {"synchronous_mode": True,
                                              "fixed_delta_seconds": .05})()

    def get_map(self):
        return self.map

    def get_settings(self):
        return self.settings

    def tick(self):
        self.index += 1
        return 100 + self.index

    def get_snapshot(self):
        return type("Snapshot", (), {"frame": 100 + self.index,
                                      "timestamp": type("Timestamp", (), {
                                          "elapsed_seconds": self.index * .05})()})()


class CaptureTest(unittest.TestCase):
    def setUp(self):
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c125763-finalizer-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        for name in ("device", "highway"):
            (self.root / (name + ".txt")).write_text(name + " original fixture\n")
        self.scene = {
            "map_sha256": hashlib.sha256(self.world.map.to_opendrive().encode()).hexdigest(),
            "reviewer": "fixture reviewer", "source_citation": "fixture only",
            "cell_id": "C125763", "control": "yield_sign", "ego_highway": "A",
            "other_highway": "B", "approach_relation": "crossing", "ego_side": "left",
            "intersection_bounds_xy_m": [0, -1, 2, 1],
            "ego_route": [[-5, 0, 0], [-1, 0, 0]],
            "other_route": [[0, -5, 0], [0, -1, 0]],
            "ego_blueprint": "vehicle.ego", "other_blueprint": "vehicle.other",
        }
        for name in ("device", "highway"):
            path = self.root / (name + ".txt")
            self.scene[name + "_source"] = {
                "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "citation": "fixture only"}
        self.packet = self.root / "reviewed-site.json"
        self.packet.write_text(json.dumps(self.scene) + "\n")
        self.ego = Actor(self.world, 10, [-2, -1, 0, 1])
        self.other = Actor(self.world, 11, [-2, -2, -1, 0])

    def test_original_clock_and_footprints_feed_measurement(self):
        output = self.root / "capture"
        receipt = capture(self.world, self.packet, self.ego, self.other, output, 4)
        self.assertEqual((receipt["first_frame"], receipt["last_frame"]), (100, 103))
        self.assertEqual(receipt["source_manifest"]["road.xodr"]["kind"], "original_native")
        timing = measure(output)
        self.assertAlmostEqual(timing["intersection_entry_time_difference_s"], -.05)
        self.assertFalse(timing["legal_verdict_claimed"])
        with self.assertRaisesRegex(ValueError, "destination"):
            capture(self.world, self.packet, self.ego, self.other, output, 4)

    def test_20_hz_and_identity_required_before_capture(self):
        self.world.settings.fixed_delta_seconds = .1
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            capture(self.world, self.packet, self.ego, self.other, self.root / "bad", 4)
        self.world.settings.fixed_delta_seconds = .05
        with self.assertRaisesRegex(ValueError, "differ"):
            capture(self.world, self.packet, self.ego, self.ego, self.root / "bad", 4)

    def test_stale_reviewed_device_source_rejected(self):
        (self.root / "device.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            capture(self.world, self.packet, self.ego, self.other, self.root / "bad", 4)

    def test_missing_intersection_bounds_rejected(self):
        del self.scene["intersection_bounds_xy_m"]
        self.packet.write_text(json.dumps(self.scene) + "\n")
        with self.assertRaisesRegex(ValueError, "bounds"):
            capture(self.world, self.packet, self.ego, self.other, self.root / "bad", 4)

    def test_saved_finalizer_seals_timing_and_rejects_stale_source(self):
        attempt = self.root / 'capture'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4)
        manifest = attempt / 'source-manifest.json'
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        output = self.root / 'entry-result.json'
        result = finalize(attempt, output, expected_manifest_sha256=digest,
                          probe_id='entry_inside')
        self.assertEqual(result['original_frame_count'], 4)
        self.assertTrue(result['diagnostic_fixture'])
        self.assertFalse(result['legal_verdict_claimed'])
        with self.assertRaises(FileExistsError):
            finalize(attempt, output, expected_manifest_sha256=digest,
                     probe_id='entry_inside')
        with self.assertRaisesRegex(ValueError, 'manifest hash mismatch'):
            finalize(attempt, self.root / 'stale.json',
                     expected_manifest_sha256='0'*64, probe_id='entry_inside')

    def test_saved_finalizer_rejects_changed_original_history(self):
        attempt = self.root / 'capture'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4)
        manifest = attempt / 'source-manifest.json'
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        with (attempt / 'ego-body-history.jsonl').open('a') as stream:
            stream.write('{}\n')
        with self.assertRaisesRegex(ValueError, 'stale original Native source'):
            finalize(attempt, self.root / 'result.json',
                     expected_manifest_sha256=digest, probe_id='entry_inside')

    def test_four_camera_original_clock_and_saved_decode(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2), (1, 2, 3)).save(stream, format='PNG')
        body = stream.getvalue()
        readers = {name: lambda frame, image=body: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        dims = {name: (2, 2) for name in CAMERAS}
        output = self.root / 'camera-capture'
        receipt = capture(self.world, self.packet, self.ego, self.other, output, 4,
                          camera_readers=readers, camera_dimensions=dims)
        self.assertEqual(receipt['camera_view_frames'], 16)
        self.assertEqual(audit_media(output, camera_dimensions=dims)['decoded_camera_frames'], 16)
        path = output / 'original-frames/approach-000001.png'
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            audit_media(output, camera_dimensions=dims)

    def test_rejects_camera_tick_mismatch(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2)).save(stream, format='PNG')
        body = stream.getvalue()
        readers = {name: lambda frame, image=body: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        readers['approach'] = lambda frame: {'frame': frame+1, 'png_bytes': body}
        with self.assertRaisesRegex(ValueError, 'camera frame identity'):
            capture(self.world, self.packet, self.ego, self.other,
                    self.root / 'wrong-camera', 4, camera_readers=readers,
                    camera_dimensions={name: (2, 2) for name in CAMERAS})


if __name__ == "__main__":
    unittest.main()
