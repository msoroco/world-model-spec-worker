"""Native readback logic tested with fake actor/sensor objects only."""
import json
import os
import queue
import tempfile
import unittest
from pathlib import Path

from native_adapter import NativeAdapter
from reviewed_scene import ASSIGNMENT, CAMERAS


class Object:
    def __init__(self, **values):
        self.__dict__.update(values)


class Actor:
    def __init__(self, ident, lane_id, station, speed):
        self.id = ident
        self.lane_id = lane_id
        self.station = station
        self.speed = speed

    def get_location(self):
        return self

    def get_velocity(self):
        return Object(x=self.speed, y=0.0, z=0.0)


class Image:
    frame = 100

    def save_to_disk(self, path):
        Path(path).write_bytes(b"fixture image")


class AdapterReadbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)
        self.adapter = NativeAdapter.__new__(NativeAdapter)
        self.adapter.output_dir = self.output
        self.adapter.world = Object(tick=lambda: 100)
        self.adapter.map = Object(get_waypoint=lambda actor, project_to_road=False:
                                  Object(road_id=21, lane_id=actor.lane_id, s=actor.station))
        self.adapter.sensors = {}
        for name in CAMERAS:
            items = queue.Queue()
            items.put(Image())
            self.adapter.sensors[name] = items
        self.adapter.frame_rows = []
        self.adapter.motion_rows = []
        self.adapter.relation_rows = []
        self.adapter.rightmost_lane_id = "-1"
        self.adapter.marked_lane_count = 2
        self.adapter.case_id = ASSIGNMENT + "__slow_middle_follower"
        self.adapter.assignment_id = ASSIGNMENT
        self.adapter.trace_id = "fixture-trace"
        self.actors = {"ego": Actor(1, -2, 20.0, 5.0),
                       "following_vehicle": Actor(2, -2, 10.0, 8.0)}

    def test_original_actor_lane_and_relation_readback(self):
        self.adapter.tick_and_capture(0, 20, self.actors, {name: name for name in CAMERAS})
        row = self.adapter.motion_rows[0]
        self.assertEqual(row["ego_lane_id"], "-2")
        self.assertEqual(row["follower_gap_m"], 10.0)
        self.assertEqual(row["follower_speed_mps"], 8.0)
        self.assertTrue(self.adapter.relation_rows[0]["immediately_behind"])
        self.assertEqual(len(self.adapter.frame_rows[0]["camera_frames"]), 4)

    def test_other_lane_is_not_immediate_follower(self):
        self.actors["following_vehicle"].lane_id = -1
        self.adapter.tick_and_capture(0, 20, self.actors, {name: name for name in CAMERAS})
        self.assertFalse(self.adapter.relation_rows[0]["immediately_behind"])

    def test_intervening_actor_breaks_immediate_relation(self):
        self.actors["slower_vehicle"] = Actor(3, -2, 15.0, 3.0)
        self.adapter.tick_and_capture(0, 20, self.actors, {name: name for name in CAMERAS})
        self.assertFalse(self.adapter.relation_rows[0]["immediately_behind"])

    def test_rejects_desynchronized_camera(self):
        self.adapter.sensors["driver_reference"].get().frame = 99
        self.adapter.sensors["driver_reference"].put(Object(frame=99))
        with self.assertRaisesRegex(ValueError, "synchronization"):
            self.adapter.tick_and_capture(0, 20, self.actors, {name: name for name in CAMERAS})


if __name__ == "__main__":
    unittest.main()
