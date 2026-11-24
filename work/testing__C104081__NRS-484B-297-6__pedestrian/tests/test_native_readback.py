import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_readback import CarlaFrameReader, CAMERAS


class Actor:
    is_alive = True
    def __init__(self, x, y):
        self.location = types.SimpleNamespace(x=x, y=y)
        self.bounding_box = types.SimpleNamespace(get_world_vertices=self.vertices)

    def get_transform(self):
        return types.SimpleNamespace(location=self.location)

    def vertices(self, transform):
        x, y = transform.location.x, transform.location.y
        return [types.SimpleNamespace(x=x + dx, y=y + dy) for dx, dy in
                ((-.1, -.1), (-.1, .1), (.1, .1), (.1, -.1))]


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.walker = Actor(10, 5)
        self.obstacle = Actor(27, 5)
        self.traffic = Actor(30, 0)
        self.camera = lambda frame: {name: frame for name in CAMERAS}
        self.transform = {"x": 0, "y": 0, "yaw_degrees": 0}

    def reader(self, **kw):
        return CarlaFrameReader(self.walker, self.obstacle, None, [self.traffic],
                                self.camera, obstruction_kind="impassable_section",
                                survey_transform=self.transform, **kw)

    def test_measured_world_readback_and_camera_join(self):
        rows = self.reader()({"frame": 101, "time_s": 5.05,
                              "position_world_xy_m": [10, 5]})
        self.assertEqual(rows["video_frames.jsonl"]["video_frame"], 0)
        self.assertEqual(rows["pedestrian_history.jsonl"]["body_vertices_world_m"][0], [9.9, 4.9])
        self.assertAlmostEqual(rows["obstruction_history.jsonl"]["sidewalk_obstruction_end_local_m"], 27.1)
        self.assertGreater(rows["traffic_history.jsonl"]["nearest_traffic_distance_m"], 20)

    def test_camera_and_body_mismatch_rejected(self):
        self.camera = lambda frame: {name: frame + (1 if name == "approach" else 0) for name in CAMERAS}
        with self.assertRaisesRegex(ValueError, "camera frames"):
            self.reader()({"frame": 101, "time_s": 5.05, "position_world_xy_m": [10, 5]})
        self.camera = lambda frame: {name: frame for name in CAMERAS}
        with self.assertRaisesRegex(ValueError, "differs from walking sample"):
            self.reader()({"frame": 101, "time_s": 5.05, "position_world_xy_m": [11, 5]})

    def test_missing_sidewalk_uses_survey_polygon(self):
        gap = [[20, 4], [20, 6], [34, 6], [34, 4]]
        reader = CarlaFrameReader(self.walker, None, None, [self.traffic], self.camera,
                                  obstruction_kind="missing_section",
                                  gap_vertices_world_m=gap, survey_transform=self.transform)
        rows = reader({"frame": 101, "time_s": 5.05,
                       "position_world_xy_m": [10, 5]})
        self.assertEqual(rows["obstruction_history.jsonl"]["sidewalk_obstruction_end_local_m"], 34)
        self.assertIsNone(rows["obstruction_history.jsonl"]["intervening_barrier_vertices_world_m"])

    def test_absent_traffic_roster_rejected(self):
        with self.assertRaisesRegex(ValueError, "traffic actor roster"):
            CarlaFrameReader(self.walker, self.obstacle, None, [], self.camera,
                             obstruction_kind="impassable_section", survey_transform=self.transform)


if __name__ == "__main__":
    unittest.main()
