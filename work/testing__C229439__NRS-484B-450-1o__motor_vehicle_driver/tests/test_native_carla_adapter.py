import hashlib
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


FOLDER = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_carla_adapter", FOLDER / "native_carla_adapter.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Map:
    name = "ReviewedMap"

    def to_opendrive(self):
        return "original-map"

    def get_waypoint(self, location, project_to_road=False):
        assert not project_to_road
        return NS(transform=NS(location=location))


class Actor:
    id = 12

    def set_autopilot(self, value):
        self.autopilot = value

    def get_transform(self):
        return NS(location=NS(x=0.0, y=0.0))

    def get_velocity(self):
        return NS(length=lambda: 0.0)

    def apply_control(self, value):
        self.control = value


class World:
    def __init__(self):
        self.actor = Actor()

    def get_map(self):
        return Map()

    def get_environment_objects(self):
        return [NS(id=41, name="reviewed-sign")]

    def get_blueprint_library(self):
        return NS(find=lambda name: NS(id=name))

    def try_spawn_actor(self, blueprint, transform):
        return self.actor


class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.api = NS(Location=lambda **kw: NS(**kw), VehicleControl=lambda **kw: kw)
        self.adapter = module.NativeParkingAdapter(self.world, self.api)
        self.site = {"map_name": "ReviewedMap", "approach_waypoints": [[0, 0], [2, 0]],
                     "parking_polygon": [[0, 0], [3, 0], [3, 3]],
                     "native_opendrive_sha256": hashlib.sha256(b"original-map").hexdigest()}
        self.device = {"native_object_id": 41, "native_object_name": "reviewed-sign",
                       "instruction_review_sha256": "1" * 64, "authority_review_sha256": "2" * 64,
                       "device_id": "sign", "exact_instruction": "NO PARKING",
                       "governed_polygon": self.site["parking_polygon"]}

    def test_reviewed_map_sign_and_vehicle_drive_request(self):
        self.assertEqual(self.adapter.verify_site(self.site)["map_name"], "ReviewedMap")
        self.assertEqual(self.adapter.install_and_read_device(self.device)["exact_instruction"], "NO PARKING")
        self.adapter.configure_effective_window("sign", "effective", [[0, 100]])
        self.assertTrue(self.adapter.read_device_effective("sign"))
        vehicle = self.adapter.spawn_driver_vehicle({"blueprint": "vehicle.test"}, [0, 0])
        self.adapter.configure_parking_route(vehicle["actor_id"], [[0, 0], [2, 0]], self.site["parking_polygon"], "park")
        self.adapter.configure_exception_cause(vehicle["actor_id"], "none")
        self.adapter.control_step()
        self.assertGreater(self.world.actor.control["throttle"], 0)

    def test_unreviewed_map_rejected(self):
        self.site["native_opendrive_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "map digest"):
            self.adapter.verify_site(self.site)

    def test_unreviewed_sign_rejected(self):
        self.device.pop("authority_review_sha256")
        with self.assertRaisesRegex(ValueError, "reviews required"):
            self.adapter.install_and_read_device(self.device)

    def test_exception_requires_source(self):
        vehicle = self.adapter.spawn_driver_vehicle({"blueprint": "vehicle.test"}, [0, 0])
        with self.assertRaisesRegex(ValueError, "exception cause packet"):
            self.adapter.configure_exception_cause(vehicle["actor_id"], "police_direction")


if __name__ == "__main__":
    unittest.main()
