import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_scene_adapter import CarlaSceneAdapter, _vertices
from camera_sources import CAMERAS, DIMENSIONS


class Vec:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Rotation:
    def __init__(self, pitch=0, yaw=0, roll=0):
        self.pitch, self.yaw, self.roll = pitch, yaw, roll


class Pose:
    def __init__(self, location, rotation):
        self.location, self.rotation = location, rotation


class Blueprint:
    def __init__(self, identity):
        self.id = identity
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Box:
    def get_world_vertices(self, transform):
        center = transform.location
        return [Vec(center.x + dx, center.y + dy, dz)
                for dz in (-.5, .5) for dx, dy in
                ((-1, -.5), (1, -.5), (1, .5), (-1, .5))]


class Actor:
    next_id = 10

    def __init__(self, blueprint, transform):
        self.id = Actor.next_id
        Actor.next_id += 1
        self.type_id = blueprint.id
        self.transform = transform
        self.bounding_box = Box()
        self.destroyed = False
        self.control = None
        self.listener = None
        self.stopped = False

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return Vec(3, 0, 0)

    def apply_control(self, control):
        self.control = control

    def listen(self, listener):
        self.listener = listener

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.sign = Actor(Blueprint("traffic.yield.sign"), Pose(Vec(), Vec()))
        self.sign.id = 7
        self.spawned = []
        self.landmarks = [type("Landmark", (), {"id": "yield-1", "type": "205"})()]
        self.settings = type("Settings", (), {"synchronous_mode": False,
                                               "fixed_delta_seconds": None})()

    def get_actor(self, identity):
        return self.sign if identity == 7 and not self.sign.destroyed else None

    def get_map(self):
        return self

    def get_all_landmarks(self):
        return self.landmarks

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        return self

    def find(self, identity):
        return Blueprint(identity)

    def spawn_actor(self, blueprint, transform, **kwargs):
        actor = Actor(blueprint, transform)
        self.spawned.append((actor, kwargs, blueprint.attributes.copy()))
        return actor

    def cast_ray(self, origin, target):
        return [type("Hit", (), {"actor_id": self.spawned[1][0].id})()]

    def get_snapshot(self):
        return type("Snapshot", (), {"timestamp": type("Time", (),
                                                     {"elapsed_seconds": 1.0})()})()


def pose(x, y):
    return {"location": {"x": x, "y": y, "z": 1},
            "rotation": {"pitch": 0, "yaw": 0, "roll": 0}}


def reviewed_site():
    return {"native_scene": {
        "ego": {"blueprint_id": "vehicle.ego", "transform": pose(0, 0)},
        "through_vehicle": {"blueprint_id": "vehicle.through", "transform": pose(6, 0)},
        "yield_sign_actor_id": 7,
        "cameras": {name: {"attach_to": "ego", "transform": pose(0, 0),
                           "fov_degrees": 90} for name in CAMERAS}}}


class Image:
    def __init__(self, name, frame=100):
        self.frame = frame
        self.timestamp = 1.0
        self.width, self.height = DIMENSIONS[name]
        self.raw_data = b"\x00\x00\xff\xff" * (self.width * self.height)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.carla = type("Carla", (), {"Location": Vec, "Rotation": Rotation,
                                        "Transform": Pose,
                                        "VehicleControl": staticmethod(lambda **kwargs: kwargs)})()
        self.world = World()
        self.site = reviewed_site()
        self.adapter = CarlaSceneAdapter(self.carla)

    def test_source_gated_synchronous_scene_and_original_pixels(self):
        self.adapter.configure(self.world, self.site)
        self.assertTrue(self.world.settings.synchronous_mode)
        self.assertEqual(self.world.settings.fixed_delta_seconds, .05)
        owned = self.adapter.spawn(self.world, self.site)
        self.assertEqual(len(owned), 6)
        for name in CAMERAS:
            self.adapter.sensor_actors[name].listener(Image(name))
        observation = self.adapter.observe(self.world, owned, 100)
        self.assertFalse(observation["raw_tick"]["visibility_probe"]["occluded"])
        self.assertEqual(set(observation["cameras"]), set(CAMERAS))
        self.assertEqual(set(observation["raw_tick"]["camera_raw_bgra_sha256"]), set(CAMERAS))
        self.assertEqual(observation["raw_tick"]["through_vehicle"]["velocity_xy_mps"], [3, 0])
        for data in observation["cameras"].values():
            self.assertTrue(data.startswith(b"\x89PNG"))
        self.adapter.apply_control(owned, {"throttle": .2, "brake": 0, "steer": 0,
                                           "through_control": {"throttle": .4, "brake": 0,
                                                               "steer": 0}})
        self.assertEqual(self.adapter.ego.control["throttle"], .2)
        self.assertEqual(self.adapter.through.control["throttle"], .4)
        for actor in reversed(owned):
            self.adapter.destroy(actor)
        self.assertTrue(all(actor.destroyed for actor in owned))
        self.assertTrue(all(self.adapter.sensor_actors[name].stopped for name in CAMERAS))

    def test_missing_reviewed_sign_and_camera_source_refused(self):
        self.site["native_scene"]["yield_sign_actor_id"] = 8
        with self.assertRaisesRegex(ValueError, "yield sign"):
            self.adapter.configure(self.world, self.site)
        self.site = reviewed_site()
        del self.site["native_scene"]["cameras"]["approach"]
        with self.assertRaisesRegex(ValueError, "four reviewed camera"):
            self.adapter.configure(self.world, self.site)

    def test_stale_camera_frame_rejected(self):
        self.adapter.configure(self.world, self.site)
        owned = self.adapter.spawn(self.world, self.site)
        self.adapter.sensor_actors["overview"].listener(Image("overview", frame=99))
        with self.assertRaisesRegex(ValueError, "camera frame differs"):
            self.adapter.observe(self.world, owned, 100)

    def test_reviewed_static_yield_landmark_readback(self):
        self.site["native_scene"].pop("yield_sign_actor_id")
        self.site["native_scene"]["yield_sign_landmark_id"] = "yield-1"
        self.adapter.configure(self.world, self.site)
        owned = self.adapter.spawn(self.world, self.site)
        for name in CAMERAS:
            self.adapter.sensor_actors[name].listener(Image(name))
        observation = self.adapter.observe(self.world, owned, 100)
        self.assertTrue(observation["raw_tick"]["sign_present"])
        self.world.landmarks = []
        for name in CAMERAS:
            self.adapter.sensor_actors[name].listener(Image(name))
        later = self.adapter.observe(self.world, owned, 100)
        self.assertFalse(later["raw_tick"]["sign_present"])

    def test_pitched_body_keeps_extreme_original_xy_corners(self):
        actor = Actor(Blueprint("vehicle.pitched"), Pose(Vec(), Rotation()))
        actor.bounding_box = type("PitchedBox", (), {
            "get_world_vertices": lambda self, transform: [
                Vec(-1, -.5), Vec(1, -.5), Vec(1, .5), Vec(-1, .5),
                Vec(-.8, -.7), Vec(1.2, -.3), Vec(.8, .7), Vec(-1.2, .3)]})()
        footprint = _vertices(actor, "pitched")
        self.assertGreaterEqual(len(footprint), 4)
        self.assertIn([-1.2, .3], footprint)
        self.assertIn([1.2, -.3], footprint)


if __name__ == "__main__":
    unittest.main()
