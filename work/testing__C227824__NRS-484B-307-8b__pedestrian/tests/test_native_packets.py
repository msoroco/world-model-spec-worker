import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_packets import PacketWriter, sample_tick, source_hashes
from saved_entry import CAMERAS, build_report


CASE = "testing__C227824__NRS-484B-307-8b__pedestrian__red_no_device_entry"


class Walker:
    id = 11

    def __init__(self):
        self.x = -1.6

        class Box:
            def get_world_vertices(box, transform):
                x = transform.location.x
                return [SimpleNamespace(x=x + dx, y=3 + dy, z=dz)
                        for dx in (-.2, .2) for dy in (-.2, .2) for dz in (0, 1.7)]

        self.bounding_box = Box()

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x))


class Head:
    id = 5

    def get_state(self):
        return "Red"


def scene():
    return {"law_id": "NRS-484B-307-8b", "cell_id": "C227824", "actor": "pedestrian",
            "case_id": CASE, "highway_polygon_xy_m": [[0, 0], [8, 0], [8, 8], [0, 8]],
            "route_id": "crossing-1", "facing_head_id": 5,
            "governing_pedestrian_device_ids": [],
            "device_inventory_review": {"complete": True, "source_sha256": "a" * 64}}


def snapshot(frame):
    return SimpleNamespace(frame=frame, timestamp=SimpleNamespace(elapsed_seconds=frame * .05))


def images(frame):
    return {name: SimpleNamespace(frame=frame, width=1280, height=720) for name in CAMERAS}


class NativePacketTests(unittest.TestCase):
    def setUp(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.attempt = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_mock_native_tick_packets_feed_saved_measurement(self):
        exact = scene()
        (self.attempt / "scene.json").write_text(json.dumps(exact) + "\n")
        (self.attempt / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        walker = Walker()
        writer = PacketWriter(self.attempt)
        for frame, x in ((1, -1.6), (2, .5), (3, 1.5)):
            walker.x = x
            writer.append(sample_tick(exact, walker, Head(), [], snapshot(frame), images(frame)))
        writer.close()
        for name in CAMERAS:
            (self.attempt / (name + ".mkv")).write_bytes(b"synthetic video placeholder")
        (self.attempt / "acquisition.json").write_text(json.dumps(source_hashes(self.attempt)) + "\n")
        report = build_report(self.attempt)
        self.assertEqual(report["measurement"]["first_entry"]["frame"], 2)
        self.assertEqual(report["sample_count"], 3)
        self.assertTrue(report["diagnostic_fixture"])
        self.assertFalse(report["actual_pixels_verified"])

    def test_stale_camera_rejected_before_packet_write(self):
        walker = Walker()
        frames = images(1)
        frames["approach"].frame = 0
        with self.assertRaisesRegex(ValueError, "stale or missing"):
            sample_tick(scene(), walker, Head(), [], snapshot(1), frames)

    def test_duplicate_frame_and_existing_packet_rejected(self):
        walker = Walker()
        writer = PacketWriter(self.attempt)
        writer.append(sample_tick(scene(), walker, Head(), [], snapshot(1), images(1)))
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            writer.append(sample_tick(scene(), walker, Head(), [], snapshot(1), images(1)))
        writer.close()
        with self.assertRaisesRegex(ValueError, "already exists"):
            PacketWriter(self.attempt)


if __name__ == "__main__":
    unittest.main()
