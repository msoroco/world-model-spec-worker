"""Source-shaped Native adapter contract tests; no physical claim."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from native_capture import VIEWS, capture, sha


def body(inside):
    x = 1 if inside else -3
    return [[x, 4], [x + 1, 4], [x + 1, 5], [x, 5]]


class FakeAdapter:
    def __init__(self, broken=False):
        self.index = 0
        self.broken = broken
        self.destroyed = []
        self.closed = False

    def setup(self, config, site):
        self.site = site

    def spawn_pair(self, site, config):
        return {"ego": 11, "other": 12}

    def attach_cameras(self, actors, cameras):
        return {name: name for name in VIEWS}

    def apply_timing_control(self, actors, site, control, index):
        assert index == self.index

    def tick_and_read(self, actors, cameras):
        i = self.index
        self.index += 1
        frame = 100 + i + (1 if self.broken and i == 7 else 0)
        t = i / 20
        return {"frame": frame, "time_s": t,
                "ego": {"id": 11, "road_id": 3, "body_corners_xy_m": body(i >= 20)},
                "other": {"id": 12, "road_id": 4, "body_corners_xy_m": body(i >= 22)},
                "camera_png": {name: b"\x89PNG\r\n\x1a\nsource-shaped" for name in VIEWS},
                "trace": {"frame": frame, "time_s": t},
                "video_frame": {"carla_frame": frame, "time_s": t}}

    def finalize_media(self, output, views, count):
        result = {}
        for name in (*views, "raw"):
            path = output / (name + ".mkv")
            path.write_bytes(b"source-shaped-test-media")
            result[name] = path
        return result

    def destroy(self, actor):
        self.destroyed.append(actor)

    def close(self):
        self.closed = True
        return True


class NativeContractTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / ".runtime-work/c125745-250-2/tmp"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name)
        (self.attempt / "construction.json").write_text("{}\n")
        self.case = "testing__C125745__NRS-484B-250-2__motor_vehicle_driver__entry_inside"
        self.config = {"selected_case_id": self.case, "cameras": [{"name": x} for x in VIEWS]}
        self.site = {"map_source_sha256": "source-map", "intersection_source_sha256": "source-polygon",
                     "highway_source_sha256": "source-highways", "device_source_sha256": "source-device",
                     "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
                     "ego_actor_id": 11, "other_actor_id": 12,
                     "ego_road_id": 3, "other_road_id": 4}
        self.site_path = self.attempt / "site-reviewed.json"
        self.site_path.write_text(json.dumps(self.site) + "\n")

    def test_900_frame_two_actor_capture_and_owner_release(self):
        adapter = FakeAdapter()
        result = capture(adapter, self.config, self.site, self.site_path,
                         sha(self.site_path), self.attempt)
        self.assertEqual(result["frame_count"], 900)
        self.assertAlmostEqual(result["entry_timing"], -.1)
        self.assertEqual(adapter.destroyed, [12, 11])
        self.assertTrue(adapter.closed)
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_frame_gap_fails_closed_and_restores(self):
        adapter = FakeAdapter(broken=True)
        with self.assertRaisesRegex(ValueError, "frame/time gap"):
            capture(adapter, self.config, self.site, self.site_path,
                    sha(self.site_path), self.attempt)
        self.assertEqual(adapter.destroyed, [12, 11])
        self.assertTrue(adapter.closed)


if __name__ == "__main__":
    unittest.main()
