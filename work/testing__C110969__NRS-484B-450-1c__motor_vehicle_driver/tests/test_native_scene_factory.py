import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_scene_factory as factory


class Actor:
    type_id = "sensor.camera.rgb"
    attributes = {"image_size_x": "1920", "image_size_y": "1080"}

    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class Blueprint:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Library:
    def find(self, name):
        return Blueprint(name)


class World:
    def __init__(self):
        self.settings = types.SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.spawned = []
        self.applied = []

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.applied.append((settings.synchronous_mode, settings.fixed_delta_seconds))

    def get_map(self):
        return types.SimpleNamespace(name="reviewed-map")

    def get_blueprint_library(self):
        return Library()

    def spawn_actor(self, blueprint, pose, attach_to=None):
        actor = Actor()
        actor.attributes = dict(blueprint.attributes)
        self.spawned.append((blueprint.name, pose, attach_to, actor))
        return actor


def packets(case_id):
    route = {"case_id": case_id, "map_id": "reviewed-map", "vehicle_blueprint": "vehicle.demo",
             "spawn": {"x": -10, "y": 0, "z": 0.2, "yaw_deg": 0}}
    boundary = {"map_id": "reviewed-map"}
    cameras = {"case_id": case_id, "map_id": "reviewed-map", "placement_reviewed": True,
               "source_refs": ["reviewed placement"], "cameras": {
                   name: {"pose": {"x": 0, "y": 0, "z": 2, "yaw_deg": 0},
                          "attach_to": "ego" if name != "reference_corner" else "world",
                          "fov_deg": 90, "source_refs": ["reviewed pose"]}
                   for name in factory.CAMERAS}}
    return route, boundary, cameras


class FactoryTests(unittest.TestCase):
    def test_refuses_unreviewed_camera_before_spawn(self):
        case = "testing__C110969__NRS-484B-450-1c__motor_vehicle_driver__inside_stop"
        route, boundary, cameras = packets(case)
        cameras["placement_reviewed"] = False
        world = World()
        with patch.object(factory, "validate_route", return_value={}):
            with self.assertRaisesRegex(ValueError, "reviewed exact camera"):
                factory.run_native(world, object(), route, boundary, cameras,
                                   object(), case, "run", Path("/ignored"))
        self.assertFalse(world.spawned)

    def test_exact_spawn_profile_and_cleanup(self):
        case = "testing__C110969__NRS-484B-450-1c__motor_vehicle_driver__inside_stop"
        route, boundary, cameras = packets(case)
        world = World()
        carla = types.SimpleNamespace(
            Transform=lambda loc, rot: (loc, rot),
            Location=lambda **kwargs: kwargs, Rotation=lambda **kwargs: kwargs,
            VehicleControl=lambda **kwargs: kwargs)
        observer = types.SimpleNamespace(observe=lambda *_: {})
        with patch.object(factory, "validate_route", return_value={}), \
             patch.object(factory, "NativeCameraAdapter") as adapter, \
             patch.object(factory, "NativeMediaWriter") as writer, \
             patch.object(factory, "DestinationController"), \
             patch.object(factory, "acquire", return_value={"frame_count": 900}) as acquire:
            result = factory.run_native(world, carla, route, boundary, cameras,
                                        observer, case, "run", Path("/ignored"))
        self.assertEqual(result["frame_count"], 900)
        self.assertEqual([entry[0] for entry in world.spawned],
                         ["vehicle.demo"] + ["sensor.camera.rgb"] * 4)
        self.assertEqual([entry[0] for entry in world.applied], [True, False])
        self.assertTrue(all(entry[3].destroyed for entry in world.spawned))
        self.assertEqual(world.spawned[3][2], None)
        self.assertEqual(world.spawned[1][2], world.spawned[0][3])
        for name, size in factory.CAMERAS.items():
            index = list(factory.CAMERAS).index(name) + 1
            attrs = world.spawned[index][3].attributes
            self.assertEqual((attrs["image_size_x"], attrs["image_size_y"]),
                             tuple(map(str, size)))
        adapter.return_value.close.assert_called_once()
        acquire.assert_called_once()
        writer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
