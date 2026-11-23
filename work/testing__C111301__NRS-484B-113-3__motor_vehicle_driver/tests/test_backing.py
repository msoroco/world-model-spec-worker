import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


geometry = module("backing_geometry")
controller = module("backing_controller")
measurements = module("backing_measurements")
import sys
sys.path.insert(0, str(ROOT))
native = module("native_backing")


def point(x, y):
    return {"x_m": x, "y_m": y, "source_ref": "map:waypoint", "junction_id": 11}


def packet():
    return {"map_sha256": "a" * 64, "map_name": "OriginalTown", "junction_id": 11,
            "vehicle_blueprint_id": "vehicle.audi.a2", "pedestrian_blueprint_id": "walker.pedestrian.0001",
            "vehicle_reverse_route": [point(5, 0), point(0, 0)],
            "pedestrian_route": [point(2, -3), point(2, 3)],
            "vehicle_half_width_m": 1.0, "pedestrian_radius_m": .3,
            "control_source": "original:intersection-control"}


class Vehicle:
    def __init__(self):
        self.controls = []

    def apply_control(self, command):
        self.controls.append(command)


def frames(brake):
    return [{"frame": i, "time_s": i * .05, "vehicle_actor_id": 7,
             "pedestrian_actor_id": 8, "vehicle_xy": [5-i*.1, 0],
             "pedestrian_xy": [2, -.5+i*.1], "vehicle_velocity_xy": [-1 if not brake else -.2, 0],
             "vehicle_forward_xy": [1, 0], "pedestrian_velocity_xy": [0, 1],
             "brake": float(brake), "reverse_gear": True, "pedestrian_in_corridor": True}
            for i in range(3)]


class BackingTests(unittest.TestCase):
    def test_original_route_conflict(self):
        self.assertTrue(geometry.validate(packet())["route_conflict"])
        missing = packet()
        missing["pedestrian_route"] = [point(2, 4), point(2, 6)]
        with self.assertRaisesRegex(ValueError, "misses"):
            geometry.validate(missing)

    def test_original_source_and_actor_identity_required(self):
        incomplete = packet()
        incomplete.pop("map_sha256")
        with self.assertRaises(ValueError):
            geometry.validate(incomplete)
        wrong_actor = packet()
        wrong_actor["pedestrian_blueprint_id"] = "vehicle.audi.a2"
        with self.assertRaises(ValueError):
            geometry.validate(wrong_actor)

    def test_controller_commands_reverse_hold_and_release(self):
        vehicle = Vehicle()
        yielding = controller.BackingController(yield_for_pedestrian=True)
        self.assertEqual(yielding.step(vehicle, pedestrian_in_corridor=True, phase="backing")["brake"], 1.0)
        self.assertGreater(yielding.step(vehicle, pedestrian_in_corridor=False, phase="backing")["throttle"], 0)
        continuing = controller.BackingController(yield_for_pedestrian=False)
        self.assertGreater(continuing.step(vehicle, pedestrian_in_corridor=True, phase="backing")["throttle"], 0)
        self.assertEqual(len(vehicle.controls), 3)

    def test_measured_backing_and_comparison(self):
        kwargs = {"map_sha256": "a" * 64, "vehicle_actor_id": 7, "pedestrian_actor_id": 8}
        a = measurements.measure(frames(True), source_id="original:a", **kwargs)
        b = measurements.measure(frames(False), source_id="original:b", **kwargs)
        self.assertEqual(measurements.compare(a,b)["legal_judgment"], "unresolved")
        with self.assertRaisesRegex(ValueError, "distinct"):
            measurements.compare(a,a)

    def test_missing_frames_rejected(self):
        original = frames(True)
        original[0].pop("pedestrian_velocity_xy")
        with self.assertRaisesRegex(ValueError, "missing"):
            measurements.measure(original, source_id="original:a", map_sha256="a"*64,
                                 vehicle_actor_id=7, pedestrian_actor_id=8)
        stationary = frames(False)
        for row in stationary:
            row["vehicle_velocity_xy"] = [0,0]
        with self.assertRaisesRegex(ValueError, "backing not observed"):
            measurements.measure(stationary, source_id="original:a", map_sha256="a"*64,
                                 vehicle_actor_id=7, pedestrian_actor_id=8)

    def test_comparison_rejects_exposure_change(self):
        kwargs = {"map_sha256": "a"*64, "vehicle_actor_id": 7, "pedestrian_actor_id": 8}
        a = measurements.measure(frames(True), source_id="original:a", **kwargs)
        changed = frames(False)
        changed[0]["pedestrian_xy"] = [9, 9]
        b = measurements.measure(changed, source_id="original:b", **kwargs)
        with self.assertRaisesRegex(ValueError, "exposure differs"):
            measurements.compare(a,b)

    def test_native_construction_and_cleanup(self):
        class Blueprint:
            def __init__(self, name): self.id = name
        class Library:
            def find(self, name): return Blueprint(name)
        class Actor:
            def __init__(self, blueprint): self.type_id = blueprint.id; self.destroyed = False
            def destroy(self): self.destroyed = True
        class World:
            def __init__(self, fail=False): self.actors = []; self.fail = fail
            def get_map(self): return type("Map",(),{"name":"OriginalTown"})()
            def get_blueprint_library(self): return Library()
            def try_spawn_actor(self, blueprint, transform):
                if self.fail and blueprint.id.startswith("walker."): return None
                actor = Actor(blueprint); self.actors.append(actor); return actor
        world = World()
        outcome = native.construct(world,packet(),{"vehicle":object(),"pedestrian":object()})
        self.assertEqual(len(world.actors),2)
        outcome["cleanup"]()
        self.assertTrue(all(a.destroyed for a in world.actors))
        failing = World(fail=True)
        with self.assertRaisesRegex(ValueError,"spawn failed"):
            native.construct(failing,packet(),{"vehicle":object(),"pedestrian":object()})
        self.assertTrue(failing.actors[0].destroyed)
