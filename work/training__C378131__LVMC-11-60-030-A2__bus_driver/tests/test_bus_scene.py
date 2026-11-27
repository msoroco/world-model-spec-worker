"""CPU construction and missing-source probes; no CARLA connection."""

import copy
from pathlib import Path
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from native.bus_scene import ZONE_KINDS, request, validate
from native.bus_construction import constructed_scene
from native.bus_capture import apply_controls


class Blueprint:
    def has_attribute(self, *_):
        return True

    def set_attribute(self, *_):
        pass


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, road):
        self.road = road
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.actors = []

    def get_map(self):
        return SimpleNamespace(to_opendrive=lambda: self.road)

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda _: Blueprint(), filter=lambda _: [Blueprint()])

    def try_spawn_actor(self, *_):
        actor = Actor()
        self.actors.append(actor)
        return actor

    def spawn_actor(self, *_, **__):
        actor = Actor()
        self.actors.append(actor)
        return actor


class Client:
    def generate_opendrive_world(self, road):
        self.world = World(road)
        return self.world


carla = SimpleNamespace(Location=lambda **kw: kw, Rotation=lambda **kw: kw,
                        Transform=lambda *args: args)

for kind in ZONE_KINDS:
    scene = request(kind)
    assert validate(scene)["camera_count"] == 4
    client = Client()
    with constructed_scene(client, carla, scene) as actors:
        assert len(client.world.actors) == 6
        assert len(actors["cameras"]) == 4
        assert actors["designation_authority_confirmed"] is False
    assert all(actor.destroyed for actor in client.world.actors)
    assert not client.world.settings.synchronous_mode

for key, change, error in [
    ("camera", lambda scene: scene["cameras"].pop(), "four source cameras"),
    ("marker", lambda scene: scene.update(zone_id="wrong"), "loading-place marker"),
    ("rate", lambda scene: scene.update(rate_hz=10), "20 Hz duration"),
    ("claim", lambda scene: scene.update(actual_loading_confirmed=True), "claims observation"),
]:
    scene = copy.deepcopy(request("route_destination"))
    change(scene)
    try:
        validate(scene)
    except ValueError as exc:
        assert error in str(exc), (key, str(exc))
    else:
        raise AssertionError("missing rejection: " + key)

print("six bus-place construction variants and four source/claim negatives passed")

import unittest


class ExactVariantTests(unittest.TestCase):
    def test_exception_has_distinct_fault_request(self):
        baseline = request("other_street")
        emergency = request("other_street", emergency=True)
        self.assertFalse(baseline["controller"]["mechanical_fault_requested"])
        self.assertTrue(emergency["controller"]["mechanical_fault_requested"])
        self.assertEqual(validate(emergency)["camera_count"], 4)

    def test_tour_exclusion_preserves_capture_contract(self):
        baseline = request("other_street")
        tour = request("other_street", vehicle_class="tour_bus")
        self.assertNotEqual(baseline["vehicle_class_requested"], tour["vehicle_class_requested"])
        self.assertEqual(baseline["cameras"], tour["cameras"])

    def test_emergency_control_call_is_distinct(self):
        class Bus:
            def __init__(self):
                self.control = None

            def apply_control(self, value):
                self.control = value

            def get_velocity(self):
                return SimpleNamespace(x=0, y=0, z=0)

        class Passenger:
            def get_location(self):
                return SimpleNamespace(x=-10, y=-5.5)

            def apply_control(self, _):
                pass

        fake = SimpleNamespace(VehicleControl=lambda **kw: kw,
                               WalkerControl=lambda **kw: kw,
                               Vector3D=lambda *v: v,
                               VehicleDoor=SimpleNamespace(FR=1))
        normal, fault = Bus(), Bus()
        apply_controls(fake, request("other_street"), normal, Passenger(), 100)
        apply_controls(fake, request("other_street", emergency=True), fault, Passenger(), 100)
        self.assertFalse(normal.control["hand_brake"])
        self.assertTrue(fault.control["hand_brake"])
