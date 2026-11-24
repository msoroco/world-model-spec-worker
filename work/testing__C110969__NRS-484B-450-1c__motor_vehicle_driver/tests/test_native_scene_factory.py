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
    def test_exception_context_actor_requires_reviewed_physical_spec(self):
        case = "testing__C110969__NRS-484B-450-1c__motor_vehicle_driver__traffic_conflict"
        route, _, _ = packets(case)
        with self.assertRaisesRegex(ValueError, 'context actor missing'):
            factory.validate_context_actors(route, case)
        route['context_actors'] = [{'role': 'conflicting_vehicle',
            'blueprint': 'vehicle.context', 'spawn': {'x': 0, 'y': 5, 'z': 0,
                                                     'yaw_deg': 90},
            'source_refs': ['independent route review'],
            'initial_control': {'throttle': 0.2, 'brake': 0, 'steer': 0}}]
        self.assertEqual(len(factory.validate_context_actors(route, case)), 1)
        route['context_actors'][0]['initial_control']['throttle'] = 2
        with self.assertRaisesRegex(ValueError, 'initial control invalid'):
            factory.validate_context_actors(route, case)

    def test_spawns_reviewed_context_before_four_cameras(self):
        case = "testing__C110969__NRS-484B-450-1c__motor_vehicle_driver__officer_direction"
        route, boundary, cameras = packets(case)
        route['context_actors'] = [{'role': 'police_officer',
            'blueprint': 'walker.reviewed', 'spawn': {'x': 1, 'y': 1, 'z': 0,
                                                     'yaw_deg': 0},
            'source_refs': ['reviewed officer placement']}]
        world = World()
        carla = types.SimpleNamespace(
            Transform=lambda loc, rot: (loc, rot),
            Location=lambda **kwargs: kwargs, Rotation=lambda **kwargs: kwargs,
            VehicleControl=lambda **kwargs: kwargs)
        observer = types.SimpleNamespace(observe=lambda *_: {}, bind_context=lambda *_: None)
        with patch.object(factory, "validate_route", return_value={}), \
             patch.object(factory, "NativeCameraAdapter"), \
             patch.object(factory, "NativeMediaWriter"), \
             patch.object(factory, "DestinationController"), \
             patch.object(factory, "acquire", return_value={"frame_count": 900}):
            factory.run_native(world, carla, route, boundary, cameras,
                               observer, case, 'run', Path('/ignored'))
        self.assertEqual([item[0] for item in world.spawned],
                         ['vehicle.demo', 'walker.reviewed'] + ['sensor.camera.rgb'] * 4)
        self.assertTrue(all(item[3].destroyed for item in world.spawned))

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

    def test_client_wires_original_capture_before_acquisition(self):
        case = "testing__C110969__NRS-484B-450-1c__motor_vehicle_driver__inside_stop"
        route, boundary, cameras = packets(case)
        world = World()
        client = types.SimpleNamespace(get_world=lambda: world)
        carla = types.SimpleNamespace(
            Transform=lambda loc, rot: (loc, rot),
            Location=lambda **kwargs: kwargs, Rotation=lambda **kwargs: kwargs,
            VehicleControl=lambda **kwargs: kwargs)
        capture_module = types.ModuleType('pipeline_capture')
        with patch.object(factory, "validate_route", return_value={}), \
             patch.object(factory, "NativeCameraAdapter"), \
             patch.object(factory, "NativeMediaWriter"), \
             patch.object(factory, "DestinationController"), \
             patch.object(factory, "acquire", return_value={"frame_count": 900}) as acquire, \
             patch.dict(sys.modules, {'pipeline_capture': capture_module}):
            from unittest.mock import Mock
            capture_module.PipelineCapture = Mock()
            factory.run_native(world, carla, route, boundary, cameras,
                               types.SimpleNamespace(observe=lambda *_: {}),
                               case, "run", Path("/ignored"), client=client)
        capture_module.PipelineCapture.assert_called_once_with(
            client, world.spawned[0][3], Path('/ignored'), case)
        self.assertIs(acquire.call_args.kwargs['pipeline_capture'],
                      capture_module.PipelineCapture.return_value)


if __name__ == "__main__":
    unittest.main()
