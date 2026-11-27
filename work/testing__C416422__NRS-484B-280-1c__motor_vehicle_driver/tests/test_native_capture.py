import importlib.util
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


class Waypoint:
    def __init__(self, x, width=4, sidewalk=True, opposing=True, extra_opposing=False,
                 ego_yaw=0, opposing_yaw=180):
        self.road_id, self.lane_id, self.lane_width, self.lane_type = 9, -1, width, "driving"
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=0, z=0),
                                         rotation=SimpleNamespace(yaw=ego_yaw))
        self.sidewalk = sidewalk
        self.opposing = opposing
        self.extra_opposing = extra_opposing
        self.opposing_yaw = opposing_yaw

    def get_left_lane(self):
        extra = (SimpleNamespace(lane_type="driving", road_id=9, lane_id=2,
                                 lane_width=4) if self.extra_opposing else None)
        return SimpleNamespace(lane_type="driving", road_id=9, lane_id=1,
                               lane_width=4, transform=SimpleNamespace(
                                   location=SimpleNamespace(x=self.transform.location.x, y=-4),
                                   rotation=SimpleNamespace(yaw=self.opposing_yaw)),
                               get_left_lane=lambda: extra,
                               get_right_lane=lambda: None) if self.opposing else None

    def get_right_lane(self):
        return SimpleNamespace(lane_type="sidewalk", road_id=9, lane_id=2,
                               lane_width=2, transform=SimpleNamespace(
                                   location=SimpleNamespace(x=self.transform.location.x,
                                                            y=3.5))) if self.sidewalk else None


class Map:
    def __init__(self, sidewalk=True, missing=False, opposing=True, extra_opposing=False,
                 ego_yaw=0, opposing_yaw=180):
        self.sidewalk, self.missing, self.opposing = sidewalk, missing, opposing
        self.extra_opposing = extra_opposing
        self.ego_yaw, self.opposing_yaw = ego_yaw, opposing_yaw
        self.calls = []

    def get_waypoint(self, location, **kwargs):
        self.calls.append(location.x)
        if kwargs.get("lane_type") == "sidewalk":
            return SimpleNamespace(lane_type="sidewalk", road_id=9, lane_id=2,
                                   lane_width=2, transform=SimpleNamespace(
                                       location=SimpleNamespace(x=location.x, y=3.5, z=0)))
        return None if self.missing else Waypoint(location.x, sidewalk=self.sidewalk,
                                                 opposing=self.opposing,
                                                 extra_opposing=self.extra_opposing,
                                                 ego_yaw=self.ego_yaw,
                                                 opposing_yaw=self.opposing_yaw)

    def to_opendrive(self):
        return "<OpenDRIVE>reviewed</OpenDRIVE>"


class NativeGeometryTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scene = json.loads((ROOT / "scene.json").read_text())
        self.carla = SimpleNamespace(Location=lambda **values: SimpleNamespace(**values),
                                     Rotation=lambda **values: SimpleNamespace(**values),
                                     Transform=lambda location, rotation: SimpleNamespace(
                                         location=location, rotation=rotation),
                                     LaneType=SimpleNamespace(Sidewalk="sidewalk", Driving="driving"))

    def test_native_route_samples_edges_and_seals_original_map(self):
        mapping = Map()
        site = native.inspect_road(SimpleNamespace(get_map=lambda: mapping),
                                   self.carla, self.scene, self.root)
        start, end = round(self.scene["ego_start_xy_m"][0]), round(self.scene["ego_end_xy_m"][0])
        expected = list(range(start, end + 1, 5))
        if expected[-1] != end:
            expected.append(end)
        self.assertEqual(mapping.calls, expected)
        self.assertEqual(site["road"]["lateral_bounds_m"], [-6, 2])
        self.assertTrue(site["sidewalk_present"])
        self.assertEqual(site["sidewalk"]["lateral_bounds_m"], [2.5, 4.5])
        self.assertTrue(all(lane == 1 for lane in site["sample_opposing_lane_ids"]))
        self.assertEqual(native.sha(self.root / "map.xodr"), site["map_source"]["sha256"])

    def test_native_missing_sidewalk_or_road_rejected(self):
        for mapping, error in ((Map(sidewalk=False), "sidewalk"),
                               (Map(opposing=False), "one driving lane"),
                               (Map(extra_opposing=True), "additional driving lanes"),
                               (Map(ego_yaw=180), "does not drive along"),
                               (Map(opposing_yaw=0), "does not face against"),
                               (Map(missing=True), "absent")):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                native.inspect_road(SimpleNamespace(get_map=lambda m=mapping: m),
                                    self.carla, self.scene, self.root)

    def test_spawn_uses_reviewed_original_lane(self):
        site = native.inspect_road(SimpleNamespace(get_map=lambda: Map()),
                                   self.carla, self.scene, self.root)
        mapping = Map()
        ego = native.spawn_at(mapping, self.carla, site, [-30, 0])
        pedestrian = native.spawn_at(mapping, self.carla, site, [0, 3], sidewalk=True)
        self.assertEqual((ego.location.x, ego.location.y), (-30, 0))
        self.assertEqual((pedestrian.location.x, pedestrian.location.y), (0, 3))
        with self.assertRaisesRegex(ValueError, "outside reviewed Native lane"):
            native.spawn_at(mapping, self.carla, site, [0, 5], sidewalk=True)
        site["road_id"] = 10
        with self.assertRaisesRegex(ValueError, "differs from reviewed road site"):
            native.spawn_at(mapping, self.carla, site, [-30, 0])

    def test_reference_camera_faces_pedestrian_and_approach_view_has_margin(self):
        poses = {name: pose for name, _, _, pose in native.Cameras.SPECS}
        for name in ("reference_corner", "approach"):
            x, y, _, _, yaw = poses[name]
            target_bearing = math.degrees(math.atan2(3 - y, 0 - x))
            error = abs((target_bearing - yaw + 180) % 360 - 180)
            self.assertLess(error, 15)

    def test_recorder_lifecycle_requires_original_bytes(self):
        class Client:
            def __init__(self, write=True):
                self.calls, self.write = [], write

            def start_recorder(self, path, additional_data):
                self.calls.append(("start", path, additional_data))
                if self.write:
                    Path(path).write_bytes(b"original CARLA recorder bytes")

            def stop_recorder(self):
                self.calls.append(("stop",))

        path = self.root / "carla_recorder.log"
        client = Client()
        recorder = native.Recorder(client, path)
        self.assertEqual(client.calls[0], ("start", str(path), True))
        try:
            raise RuntimeError("simulated capture failure")
        except RuntimeError:
            recorder.close()
        recorder.close()
        self.assertEqual(client.calls[-1], ("stop",))
        self.assertEqual(len(client.calls), 2)
        with self.assertRaisesRegex(ValueError, "already exists"):
            native.Recorder(client, path)
        with self.assertRaisesRegex(ValueError, "bytes absent"):
            native.Recorder(Client(write=False), self.root / "missing-recorder.log").close()


if __name__ == "__main__":
    unittest.main()
