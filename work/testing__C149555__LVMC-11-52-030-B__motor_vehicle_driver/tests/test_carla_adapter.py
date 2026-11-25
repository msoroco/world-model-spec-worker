import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path.cwd() / ".runtime-work"
SCRATCH.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("carla_adapter", ROOT / "carla_adapter.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Map:
    name = "ReviewedTown"

    def __init__(self, opposite=False):
        self.xml = '<OpenDRIVE><road id="2"><lanes><laneSection><right><lane id="-1" type="driving"/></right>' + ('<left><lane id="1" type="driving"/></left>' if opposite else '') + '</laneSection></lanes></road></OpenDRIVE>'

    def to_opendrive(self):
        return self.xml

    def get_waypoint_xodr(self, road_id, lane_id, station):
        return type("Waypoint", (), {"road_id": road_id, "lane_id": lane_id})()


class World:
    def __init__(self, m):
        self.m = m

    def get_map(self):
        return self.m


class NativeAdapterTests(unittest.TestCase):
    def test_original_sample_reads_live_body_and_cargo_positions(self):
        class Point:
            def __init__(self, station):
                self.x, self.y, self.z = station, 0.0, 0.0
        class Ego:
            id = 7
            bounding_box = type("Box", (), {"get_world_vertices":
                lambda _, transform: [Point(28), Point(32)]})()
            def get_transform(self):
                return type("Transform", (), {"location": Point(30),
                                              "rotation": type("Rotation", (), {"yaw": 0.0})(),
                                              "get_right_vector": lambda _: Point(1)})()
            def get_location(self):
                return Point(30)
            def get_velocity(self):
                return type("Velocity", (), {"length": lambda _: 0.0})()
        class SampleMap(Map):
            def get_waypoint(self, location, project_to_road=False):
                return type("Waypoint", (), {"road_id": 2, "lane_id": -1,
                                               "s": location.x})()
        adapter = module.NativeCarlaAdapter(World(SampleMap()),
                                            {"native_road_id": 2, "native_lane_id": -1},
                                            {}, carla_module=object())
        adapter.ego = Ego()
        adapter.cargo = type("Cargo", (), {"id": 9, "get_location": lambda _: Point(31)})()
        snapshot = type("Snapshot", (), {"frame": 101,
                "timestamp": type("Timestamp", (), {"elapsed_seconds": 0.0})()})()
        row = adapter.sample_original(0, 101, snapshot)
        self.assertEqual((row["ego_body_station_min_m"], row["ego_body_station_max_m"]),
                         (28, 32))
        self.assertEqual(row["cargo_actor_id"], 9)
        self.assertEqual(row["cargo_position_m"], [31, 0.0, 0.0])
        self.assertEqual(row["cargo_lateral_offset_m"], 1.0)
        with self.assertRaisesRegex(module.SourceError, "frame mismatch"):
            adapter.sample_original(0, 102, snapshot)

    def test_motion_is_deferred_into_synchronized_capture(self):
        class Ego:
            id = 7
            def __init__(self):
                self.controls = []
                self.speed = 2.0
            def get_velocity(self):
                return type("Velocity", (), {"length": lambda _: self.speed})()
            def apply_control(self, value):
                self.controls.append(value)
        class Carla:
            @staticmethod
            def VehicleControl(**values):
                return values
        class RoadMap(Map):
            def get_waypoint_xodr(self, road_id, lane_id, station):
                return object()
        class TickWorld(World):
            def tick(self):
                raise AssertionError("construction must not tick before capture")
        adapter = module.NativeCarlaAdapter(
            TickWorld(RoadMap()), {"native_road_id": 2, "native_lane_id": -1}, {}, carla_module=Carla())
        adapter.ego = Ego()
        adapter.drive_to_station(7, 30.0)
        adapter.stop_and_hold(7)
        self.assertEqual(adapter.ego.controls, [])
        adapter._current_station = lambda: 5.0
        self.assertEqual(adapter.step_capture(0)["phase"], "approach")
        self.assertTrue(adapter.ego.controls[-1]["throttle"] > 0)
        adapter._current_station = lambda: 30.0
        self.assertEqual(adapter.step_capture(1)["phase"], "braking")
        adapter.ego.speed = 0.0
        self.assertEqual(adapter.step_capture(2)["phase"], "hold")
        self.assertTrue(adapter.ego.controls[-1]["hand_brake"])

    def test_native_map_and_one_way_are_checked_before_spawn(self):
        m = Map()
        s = {"native_map_name": "ReviewedTown", "approach_station_m": 5}
        adapter = module.NativeCarlaAdapter(World(m), s, {}, carla_module=object())
        adapter.assert_native_map(hashlib.sha256(m.xml.encode()).hexdigest())
        adapter.assert_one_way_lane(2, -1)
        with self.assertRaisesRegex(module.SourceError, "OpenDRIVE map seal"):
            adapter.assert_native_map("bad")
        other = module.NativeCarlaAdapter(World(Map(opposite=True)), s, {}, carla_module=object())
        with self.assertRaisesRegex(module.SourceError, "one-way"):
            other.assert_one_way_lane(2, -1)

    def test_yellow_curb_requires_sealed_original_review(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            p = Path(tmp) / "curb.json"
            observation = {"map_name": "ReviewedTown", "color": "yellow", "start_station_m": 20, "end_station_m": 40, "independent_pixel_review": True}
            p.write_text(json.dumps(observation), encoding="utf-8")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            adapter = module.NativeCarlaAdapter(World(Map()), {"curb_observation_path": str(p)}, {}, carla_module=object())
            adapter.assert_yellow_curb({"start_station_m": 20, "end_station_m": 40}, digest)
            observation["independent_pixel_review"] = False
            p.write_text(json.dumps(observation), encoding="utf-8")
            with self.assertRaisesRegex(module.SourceError, "stale original source"):
                adapter.assert_yellow_curb({"start_station_m": 20, "end_station_m": 40}, digest)


if __name__ == "__main__":
    unittest.main()
