"""CPU fake acquisition: controller calls, 900 Native joins and camera rejection."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_capture import VIEWS, capture


class Actor:
    def __init__(self, actor_id, x):
        self.id, self.x, self.controls = actor_id, x, []
        self.bounding_box = types.SimpleNamespace(
            extent=types.SimpleNamespace(x=2., y=.9, z=.7))

    def get_transform(self):
        point = types.SimpleNamespace(x=self.x, y=-2., z=0.)
        return types.SimpleNamespace(location=point,
                                     rotation=types.SimpleNamespace(yaw=0.))

    def get_velocity(self):
        return types.SimpleNamespace(x=1., y=0., z=0.)

    def apply_control(self, control):
        self.controls.append(control)


class World:
    def __init__(self, actors):
        self.frame, self.actors = 0, actors

    def get_settings(self):
        return types.SimpleNamespace(synchronous_mode=True, no_rendering_mode=False,
                                     fixed_delta_seconds=.05)

    def tick(self):
        self.frame += 1
        for actor in self.actors:
            actor.x += .05
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame,
                                     timestamp=types.SimpleNamespace(elapsed_seconds=self.frame * .05))


class Rig:
    def __init__(self, missing=False):
        self.missing = missing

    def await_frame(self, frame, time_s):
        names = VIEWS[:-1] if self.missing else VIEWS
        return {name: {"frame": frame, "time_s": time_s,
                       "sha256": "a" * 64, "raw_bgra": "raw/" + name}
                for name in names}


class FrameMap:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.stream = self.path.open("x", encoding="utf-8")
        return self

    def __exit__(self, *args):
        self.stream.close()

    def append(self, frame, time_s, camera_source_sha256):
        self.stream.write(json.dumps({"native_frame": frame, "time_s": time_s,
                                      "camera_source_sha256": camera_source_sha256}) + "\n")


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        self.ego, self.companion = Actor(1, -20.), Actor(2, -20.)
        self.scene = types.SimpleNamespace(ego=self.ego, companion=self.companion,
                                           packet={"approach_direction": 1,
                                                   "stop_line_x_m": 0., "rail_line_x_m": 10.,
                                                   "source_packet_sha256": "a" * 64,
                                                   "marked_lanes": [{"lane_id": 1}, {"lane_id": 2}]})

    def test_900_source_and_camera_joins(self):
        world = World([self.ego, self.companion])
        result = capture(world, self.scene, Rig(), self.attempt, "case",
                         lambda **kwargs: kwargs, frame_map_factory=FrameMap)
        self.assertEqual(result["frames"], 900)
        rows = [json.loads(line) for line in (self.attempt / "trace.jsonl").read_text().splitlines()]
        maps = [json.loads(line) for line in (self.attempt / "video_frames.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), len(maps))
        self.assertEqual(len(rows), 900)
        self.assertEqual(rows[-1]["frame"], maps[-1]["native_frame"])
        self.assertEqual(len(self.ego.controls), 900)
        self.assertEqual(len(self.companion.controls), 900)
        self.assertFalse(rows[-1]["physical_acceptance_claimed"])
        self.assertEqual(rows[-1]["ego"]["bbox_half_extent_m"], [2., .9, .7])

    def test_missing_fourth_camera_rejected(self):
        with self.assertRaisesRegex(ValueError, "four camera frame sources missing"):
            capture(World([self.ego, self.companion]), self.scene,
                    Rig(missing=True), self.attempt, "case",
                    lambda **kwargs: kwargs, frame_map_factory=FrameMap)

    def test_non_900_capture_rejected_before_writing(self):
        with self.assertRaisesRegex(ValueError, "900 frames"):
            capture(World([self.ego, self.companion]), self.scene, Rig(),
                    self.attempt, "case", lambda **kwargs: kwargs,
                    frame_map_factory=FrameMap, count=3)
        self.assertFalse(self.attempt.exists())


if __name__ == "__main__":
    unittest.main()
