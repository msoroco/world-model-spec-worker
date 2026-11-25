"""CPU tests of source-bound construction; fake Native state is not evidence."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "native_adapter.py"
spec = importlib.util.spec_from_file_location("c158196_native_adapter", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
ASSIGNMENT = "testing__C158196__NRS-484B-257-2__motor_vehicle_driver"
CASE = ASSIGNMENT + "__sign_within_stop"
CASE_SPEC = {"case_id": CASE, "cell_id": "C158196", "control_context": "stop_sign",
             "counterpart_start_m": 10}
SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c158196-adapter-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


class Location:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Rotation:
    def __init__(self, yaw):
        self.yaw = yaw


class Transform:
    def __init__(self, location, rotation):
        self.location, self.rotation = location, rotation


class VehicleControl:
    def __init__(self, **kwargs):
        self.values = kwargs


class Carla:
    Location = Location
    Rotation = Rotation
    Transform = Transform
    VehicleControl = VehicleControl


class Actor:
    def __init__(self, actor_id, kind):
        self.id, self.type_id = actor_id, kind
        self.controls = []
        self.destroyed = False

    def apply_control(self, value):
        self.controls.append(value.values)

    def destroy(self):
        self.destroyed = True


class Map:
    name = "TownSurvey"

    def get_waypoint(self, point, project_to_road=False):
        lane = 1 if point.y == 0 else 2
        return type("Waypoint", (), {"road_id": lane, "lane_id": -1,
                                      "transform": Transform(point, Rotation(0))})()


class Blueprints:
    def find(self, name):
        return name


class World:
    def __init__(self):
        self.map = Map()
        self.control = Actor(45, "traffic.stop")
        self.spawned = []

    def get_map(self):
        return self.map

    def get_actor(self, actor_id):
        return self.control if actor_id == self.control.id else None

    def get_blueprint_library(self):
        return Blueprints()

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(100 + len(self.spawned), blueprint)
        self.spawned.append((actor, transform))
        return actor


def docs():
    def point(x, y):
        return {"x": x, "y": y, "z": 0.1, "yaw": 0}
    return {
        "site.json": {"cell_id": "C158196", "layout": "one_way_to_two_way_intersection",
                      "through_highway": False, "native_map_name": "TownSurvey",
                      "intersection_rectangle_xy": [-2, -2, 2, 2]},
        "devices.json": {"case_id": CASE, "control_context": "stop_sign",
                         "ego_control_actor_id": 45, "sign_kind": "stop_sign",
                         "facing_road_id": 1, "facing_lane_id": -1,
                         "signal_controlling": False, "officer_controlling": False,
                         "counterpart_priority_source": {"route_road_id": 2, "unobligated": True,
                                                         "original_device_survey": "reviewed cross approach"}},
        "routes.json": {"case_id": CASE,
                        "ego_approach": {"road_id": 1, "lane_id": -1,
                                         "native_waypoints": [point(-20, 0), point(-10, 0)],
                                         "vehicle_blueprint": "vehicle.tesla.model3"},
                        "counterpart_route": {"road_id": 2, "lane_id": -1,
                                              "native_waypoints": [point(0, 10), point(0, 8)],
                                              "vehicle_blueprint": "vehicle.audi.tt"}}
    }


def bundle(root, data):
    refs = []
    for name, value in data.items():
        path = root / name
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        refs.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (root / "bundle-index.json").write_text(json.dumps({
        "format": "c158196-original-site-bundle", "cell_id": "C158196",
        "case_id": CASE, "control_context": "stop_sign", "sources": refs}, sort_keys=True) + "\n")


class AdapterTest(unittest.TestCase):
    def test_original_source_hash_and_context_required(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            bundle(root, docs())
            survey = mod.load_site(root, CASE, "stop_sign")
            self.assertEqual(survey["site"]["native_map_name"], "TownSurvey")
            with self.assertRaisesRegex(ValueError, "exact case"):
                mod.load_site(root, CASE, "yield_sign")
            (root / "devices.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                mod.load_site(root, CASE, "stop_sign")

    def test_native_readback_precedes_spawn(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            bundle(root, docs())
            survey = mod.load_site(root, CASE, "stop_sign")
            world = World()
            adapter = mod.NativeAdapter(world, Carla, survey, CASE_SPEC)
            with self.assertRaisesRegex(ValueError, "before spawn"):
                adapter.spawn_vehicle("ego", {"resolve_from_native_map": True})
            with self.assertRaisesRegex(ValueError, "map readback"):
                adapter.inspect_devices()
            self.assertEqual(adapter.inspect_intersection()["through_highway"], False)
            world.control.type_id = "traffic.traffic_light"
            with self.assertRaisesRegex(ValueError, "type differs"):
                adapter.inspect_devices()
            self.assertEqual(world.spawned, [])
            world.control.type_id = "traffic.stop"
            self.assertEqual(adapter.inspect_devices()["context"], "stop_sign")
            ego = adapter.spawn_vehicle("ego", {"resolve_from_native_map": True})
            other = adapter.spawn_vehicle("counterpart", {"resolve_from_native_map": True})
            adapter.set_target_speed(ego, 2.5)
            adapter.set_target_speed(other, 3)
            adapter.step(lambda role, actor, target, route, bounds, devices:
                         {"throttle": 0.2, "brake": 0.0, "steer": 0.0})
            self.assertEqual(len(world.spawned), 2)
            self.assertEqual(world.spawned[0][0].controls[0]["throttle"], 0.2)
            adapter.destroy()
            self.assertTrue(all(actor.destroyed for actor, _ in world.spawned))

    def test_wrong_native_map_or_priority_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            bundle(root, docs())
            survey = mod.load_site(root, CASE, "stop_sign")
            world = World()
            world.map.name = "WrongTown"
            adapter = mod.NativeAdapter(world, Carla, survey, CASE_SPEC)
            with self.assertRaisesRegex(ValueError, "Native map differs"):
                adapter.inspect_intersection()
            world.map.name = "TownSurvey"
            adapter.inspect_intersection()
            survey["devices"]["counterpart_priority_source"]["unobligated"] = False
            with self.assertRaisesRegex(ValueError, "priority"):
                adapter.inspect_devices()
            self.assertEqual(world.spawned, [])

    def test_frozen_counterpart_spacing_is_constructed(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            bundle(root, docs())
            survey = mod.load_site(root, CASE, "stop_sign")
            adapter = mod.NativeAdapter(World(), Carla, survey, dict(CASE_SPEC, counterpart_start_m=23))
            with self.assertRaisesRegex(ValueError, "frozen engineering contrast"):
                adapter.inspect_intersection()


if __name__ == "__main__":
    unittest.main()
