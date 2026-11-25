import math
import sys
import types
import unittest
from enum import IntFlag
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carla_adapter import open_session
from test_native_site import SITE


class Vec:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def distance(self, other):
        return math.sqrt((self.x-other.x)**2 + (self.y-other.y)**2 + (self.z-other.z)**2)


class Rotation:
    def __init__(self, yaw=0, pitch=0, roll=0):
        self.yaw, self.pitch, self.roll = yaw, pitch, roll


class Transform:
    def __init__(self, location, rotation):
        self.location, self.rotation = location, rotation


class Lights(IntFlag):
    RightBlinker = 1


class Blueprint:
    def __init__(self, identifier):
        self.id = identifier
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Actor:
    def __init__(self, blueprint, transform, identifier):
        self.type_id = blueprint.id
        self.transform = transform
        self.id = identifier
        self.is_alive = True
        self.destroyed = False
        self.stopped = False
        self.light_state = Lights(0)
        self.velocity = Vec()
        self.bounding_box = types.SimpleNamespace(get_world_vertices=lambda pose: [
            Vec(pose.location.x + dx, pose.location.y + dy, pose.location.z)
            for dx in (-1, 1) for dy in (-.5, .5) for _ in (0, 1)])

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return self.velocity

    def apply_control(self, control):
        self.control = control

    def get_light_state(self):
        return self.light_state

    def set_light_state(self, value):
        self.light_state = value

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.settings = types.SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = types.SimpleNamespace(cloudiness=0, precipitation=0, sun_altitude_angle=50)
        self.actors = []
        self.frame = 0

    def get_map(self):
        return types.SimpleNamespace(name="ReviewedTown")

    def get_settings(self):
        return types.SimpleNamespace(synchronous_mode=self.settings.synchronous_mode,
                                     fixed_delta_seconds=self.settings.fixed_delta_seconds)

    def apply_settings(self, value):
        self.settings = value

    def get_weather(self):
        return self.weather

    def set_weather(self, value):
        self.weather = value

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda identifier: Blueprint(identifier))

    def spawn_actor(self, blueprint, transform, attach_to=None):
        actor = Actor(blueprint, transform, len(self.actors) + 1)
        self.actors.append(actor)
        return actor

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame,
                                     timestamp=types.SimpleNamespace(elapsed_seconds=self.frame * .05))


class AdapterTests(unittest.TestCase):
    def test_lazy_session_actuation_and_restoration(self):
        world = World()
        fake = types.SimpleNamespace(
            Client=lambda host, port: types.SimpleNamespace(set_timeout=lambda timeout: None,
                                                           get_world=lambda: world),
            Location=Vec, Rotation=Rotation, Transform=Transform,
            VehicleLightState=Lights,
            VehicleControl=lambda **kwargs: types.SimpleNamespace(**kwargs),
            WeatherParameters=types.SimpleNamespace(
                ClearNoon=types.SimpleNamespace(cloudiness=0, precipitation=0, sun_altitude_angle=50),
                HardRainNoon=types.SimpleNamespace(cloudiness=90, precipitation=90, sun_altitude_angle=50)),
        )
        previous = sys.modules.get("carla")
        sys.modules["carla"] = fake
        try:
            with open_session("127.0.0.1", 2000, {"case": {}, "site": SITE}) as session:
                self.assertTrue(world.settings.synchronous_mode)
                ego = session.spawn_ego(SITE["ego_blueprint_id"], SITE["approach_start_xyz"])
                self.assertEqual(ego["actor_id"], 1)
                self.assertEqual(len(session.sensors), 4)
                self.assertEqual(len(session.read_ego_state()["body_vertices_m"]), 8)
                session.set_weather("rain")
                self.assertEqual(session.read_weather(), "rain")
                session.command_drive(SITE["turn_vertex_xyz"])
                session.request_right_signal(True)
                self.assertTrue(session.read_right_signal())
                session.request_right_signal(False)
                self.assertFalse(session.read_right_signal())
                self.assertEqual(session.tick()["frame"], 1)
            self.assertFalse(world.settings.synchronous_mode)
            self.assertTrue(session.restoration_verified)
            self.assertEqual(world.weather.precipitation, 0)
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            self.assertTrue(all(sensor.stopped for sensor in world.actors[1:]))
        finally:
            if previous is None:
                sys.modules.pop("carla", None)
            else:
                sys.modules["carla"] = previous


if __name__ == "__main__":
    unittest.main()
