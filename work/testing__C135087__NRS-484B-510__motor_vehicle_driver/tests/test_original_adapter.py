"""CPU readback test for the Native adapter's per-frame joins."""

import io
import queue
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_adapter import OriginalAdapter, _inside_polygon


class Point:
    def __init__(self, x, y, z=0): self.x, self.y, self.z = x, y, z


class Actor:
    def __init__(self, actor_id, location, speed=0):
        self.id, self.location, self.speed = actor_id, location, speed

    def get_transform(self): return type("Transform", (), {"location": self.location})()
    def get_velocity(self): return Point(self.speed, 0, 0)
    def get_parent(self): return None


class Image:
    width = height = 1
    raw_data = bytes((0, 0, 255, 255))

    def __init__(self, frame, timestamp):
        self.frame, self.timestamp = frame, timestamp


class Encoder:
    def __init__(self): self.stdin = io.BytesIO()


class NativeAdapterTests(unittest.TestCase):
    def test_polygon_is_physical_geometry_only(self):
        box = [[10, -2], [30, -2], [30, 2], [10, 2]]
        self.assertTrue(_inside_polygon((16, 0, 0), box))
        self.assertFalse(_inside_polygon((5, 0, 0), box))

    def test_original_frame_camera_and_trace_join(self):
        adapter = OriginalAdapter.__new__(OriginalAdapter)
        binding = {"approach_route": [{"station_m": -5, "location_m": [-5, 0, 0]},
                                      {"station_m": 35, "location_m": [35, 0, 0]}],
                   "observation_tolerances_m": {"station": 2, "door": 1, "access": 2},
                   "passenger_door_m": [16, 1, 0],
                   "entrant_access_polygon_m": [[10, -2], [30, -2], [30, 2], [10, 2]]}
        class World:
            frame = 99

            def tick(self):
                self.frame += 1
                return self.frame

            def get_snapshot(self):
                return type("Snapshot", (), {"frame": self.frame,
                        "timestamp": type("Timestamp", (), {"elapsed_seconds":
                                    10 + (self.frame - 100) / 20})()})()

        adapter.world = type("Placement", (), {"world": World(), "binding": binding})()
        adapter.plan = type("Plan", (), {"case_id": "test", "map_id": "reviewed-map",
                          "zone_start_m": 10, "zone_end_m": 30})()
        adapter.actors = {"subject": Actor(1, Point(16, 0)),
                          "entrant": Actor(2, Point(9, 0)),
                          "passenger": Actor(3, Point(16, 1))}
        adapter.sensors = {view: object() for view in adapter.VIEWS}
        adapter.camera_queues = {view: queue.Queue() for view in adapter.VIEWS}
        adapter.encoders = {view: Encoder() for view in (*adapter.VIEWS, "raw")}
        adapter.pipeline = type("Pipeline", (), {"capture": lambda _, frame, time_s:
                           {"frame": frame, "time_s": time_s}})()
        adapter.last_frame = None
        adapter.start_time = None
        adapter.sample_index = 0
        for frame in (100, 101):
            for view in adapter.VIEWS:
                adapter.camera_queues[view].put(Image(frame, 10 + (frame - 100) / 20))
            sample = adapter.tick_and_read(adapter.actors, adapter.sensors)
            self.assertEqual(sample["video_frame"]["video_frame"], frame - 100)
            self.assertEqual(sample["trace"]["frame"], frame)
            self.assertEqual(set(sample["camera_png"]), set(adapter.VIEWS))
            self.assertTrue(all(value.startswith(b"\x89PNG\r\n\x1a\n")
                                for value in sample["camera_png"].values()))
            self.assertEqual(sample["state"]["passenger_boarding_state"], "at_door")
            self.assertTrue(sample["state"]["entrant_access_blocked"])


if __name__ == "__main__":
    unittest.main()
