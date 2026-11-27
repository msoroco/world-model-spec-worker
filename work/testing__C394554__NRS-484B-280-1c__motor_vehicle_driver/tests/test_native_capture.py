import importlib.util
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("transit_native", ROOT / "native_capture.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


def loc(x, y, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


class Actor:
    def __init__(self, actor_id, blueprint, position, body):
        self.id, self.type_id = actor_id, blueprint
        self.position, self.body = position, body
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda transform: self.body)

    def get_transform(self):
        return SimpleNamespace(location=self.position)


class Waypoint:
    def __init__(self, x, y=0, yaw=0, lane_id=-1):
        self.road_id, self.lane_id, self.lane_width = 9, lane_id, 4
        self.transform = SimpleNamespace(location=loc(x, y), rotation=SimpleNamespace(yaw=yaw))


class Map:
    def __init__(self):
        self.calls = []

    def get_waypoint(self, position):
        self.calls.append(position.x)
        return Waypoint(position.x)

    def to_opendrive(self):
        return "<OpenDRIVE>original</OpenDRIVE>"


class NativeTransitTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scene = json.loads((ROOT / "scene.json").read_text())
        self.carla = SimpleNamespace(Location=lambda **values: SimpleNamespace(**values))
        self.map = Map()
        self.world = SimpleNamespace(get_map=lambda: self.map)
        self.body = [loc(0, 3), loc(1, 3), loc(1, 4), loc(0, 4)]
        self.bus = Actor(40, "vehicle.mitsubishi.fusorosa", loc(1, 4.5), self.body)
        self.stop = Actor(30, "static.prop.busstop", loc(0, 7), [])

    def test_native_map_stop_and_bus_readback(self):
        site = native.inspect_road(self.world, self.carla, self.scene, self.root,
                                   self.bus, self.stop)
        self.assertEqual(site["road"]["road_id"], 9)
        self.assertEqual(site["stop"]["actor_id"], 30)
        self.assertEqual(site["bus"]["blueprint_id"], "vehicle.mitsubishi.fusorosa")
        self.assertEqual(site["bus"]["door_region_m"]["y_max"], 4)
        self.assertEqual(site["map_source"]["sha256"], native.sha(self.root / "map.xodr"))
        start, end = round(self.scene["ego_start_xy_m"][0]), round(self.scene["ego_end_xy_m"][0])
        expected = list(range(start, end + 1, 5))
        if expected[-1] != end:
            expected.append(end)
        self.assertEqual(self.map.calls, expected)

    def test_native_missing_bus_stop_asset_rejected(self):
        self.stop.type_id = "static.prop.trafficcone"
        with self.assertRaisesRegex(ValueError, "bus stop blueprint"):
            native.inspect_road(self.world, self.carla, self.scene, self.root,
                                self.bus, self.stop)

    def test_original_lane_center_projection_and_direction_are_checked(self):
        self.map.get_waypoint = lambda position: Waypoint(position.x, y=1.75)
        site = native.inspect_road(self.world, self.carla, self.scene, self.root,
                                   self.bus, self.stop)
        self.assertEqual(site["ego_lane_start_position_m"][:2],
                         [self.scene["ego_start_xy_m"][0], 1.75])
        self.map.get_waypoint = lambda position: Waypoint(position.x, y=1.75, yaw=180)
        with self.assertRaisesRegex(ValueError, "points away"):
            native.inspect_road(self.world, self.carla, self.scene, self.root,
                                self.bus, self.stop)
        self.map.get_waypoint = lambda position: Waypoint(position.x, y=4.5)
        with self.assertRaisesRegex(ValueError, "route absent"):
            native.inspect_road(self.world, self.carla, self.scene, self.root,
                                self.bus, self.stop)

    def test_encounter_cameras_point_at_original_bus_and_stop(self):
        carla = SimpleNamespace(Location=lambda **values: SimpleNamespace(**values),
                                Rotation=lambda **values: SimpleNamespace(**values),
                                Transform=lambda location, rotation: SimpleNamespace(
                                    location=location, rotation=rotation))
        site = {"stop": {"position_m": [0, 7, 0]},
                "bus": {"position_m": [1, 4.5, 0]}}
        for name, _, _, pose in native.Cameras.SPECS:
            if name not in ("approach", "reference_corner"):
                continue
            transform = native.Cameras.transform(name, pose, site, carla)
            dx = 0.5 - transform.location.x
            dy = 5.75 - transform.location.y
            angle = math.degrees(math.atan2(dy, dx))
            self.assertAlmostEqual(transform.rotation.yaw, angle)
            self.assertLess(transform.rotation.pitch, 0)
        self.assertGreater(native.Cameras.transform("reference_corner",
            native.Cameras.SPECS[2][3], site, carla).rotation.yaw, 90)

    def test_recorder_has_fresh_start_and_nonempty_stop(self):
        path = self.root / "carla_recorder.log"
        calls = []
        client = SimpleNamespace(start_recorder=lambda name, additional: (
            calls.append((name, additional)) or True),
            stop_recorder=lambda: (calls.append("stop"), path.write_text("native recorder bytes")))
        self.assertEqual(native.start_recorder(client, self.root), path)
        self.assertEqual(calls, [(str(path), True)])
        native.stop_recorder(client, path)
        self.assertEqual(calls[-1], "stop")
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            native.start_recorder(client, self.root)
        path.unlink()
        bad = SimpleNamespace(start_recorder=lambda name, additional: False)
        with self.assertRaisesRegex(RuntimeError, "failed to start"):
            native.start_recorder(bad, self.root)
        with self.assertRaisesRegex(RuntimeError, "missing or empty"):
            native.stop_recorder(SimpleNamespace(stop_recorder=lambda: None), path)


if __name__ == "__main__":
    unittest.main()
