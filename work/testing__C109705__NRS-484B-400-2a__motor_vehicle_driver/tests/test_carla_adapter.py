"""CPU owner and exact callback tests for the lazy Native CARLA bridge."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carla_adapter import NativeCarlaAdapter
import runner


class Blueprint:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Ego:
    id = 7
    type_id = 'vehicle.test'
    is_alive = True

    def __init__(self):
        self.transform = NS(location=NS(x=0., y=0., z=0.),
                            rotation=NS(yaw=0., pitch=0., roll=0.))
        self.bounding_box = NS(get_world_vertices=lambda _: [
            NS(x=x, y=y, z=0.) for x, y in
            ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5))])
        self.controls = []
        self.destroyed = False

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return NS(x=0., y=0., z=0.)

    def apply_control(self, command):
        self.controls.append(command)

    def destroy(self):
        self.destroyed = True


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.settings = NS(synchronous_mode=False, fixed_delta_seconds=None)
        self.ego = Ego()
        self.sensors = []
        self.frame = 99

    def get_map(self):
        return NS(name='TownTest', get_waypoint=lambda _: NS(road_id='A'))

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = copy.copy(settings)

    def get_blueprint_library(self):
        return NS(find=lambda name: Blueprint(name))

    def try_spawn_actor(self, bp, _):
        if bp.name == 'sensor.camera.rgb':
            sensor = Sensor()
            self.sensors.append(sensor)
            return sensor
        return self.ego

    def tick(self):
        self.frame += 1
        image = NS(frame=self.frame, timestamp=(self.frame - 100) * .05,
                   width=2, height=2, raw_data=bytes((0, 0, 255, 255)) * 4)
        for sensor in self.sensors:
            sensor.callback(image)
        return self.frame

    def get_snapshot(self):
        return NS(frame=self.frame,
                  timestamp=NS(elapsed_seconds=(self.frame - 100) * .05))


class CarlaAdapterTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        carla = NS(Location=lambda **kw: NS(**kw), Rotation=lambda **kw: NS(**kw),
                   Transform=lambda location, rotation: NS(location=location,
                                                           rotation=rotation),
                   VehicleControl=lambda **kw: NS(**kw))
        pose = {'x': 0., 'y': 0., 'z': 1., 'yaw': 0.}
        self.packet = {'spawn_transform': pose,
                       'route_transforms': [
                           {'waypoint_id': 1, 'x': 0., 'y': 0.},
                           {'waypoint_id': 2, 'x': 5., 'y': 0.}],
                       'camera_transforms': {name: pose for name in
                                             ('overview', 'approach', 'reference_corner',
                                              'driver_reference')},
                       'road_geometry': {'intersection_xy_m': [[0, 0]]},
                       'context': {'approach_road_id': 'A',
                                   'departure_road_id': 'B'}}
        self.config = {'selected_case_id': 'exact', 'cameras': [
            {'name': name, 'width': 2, 'height': 2} for name in
            ('overview', 'approach', 'reference_corner', 'driver_reference')]}
        self.plan = {'map_name': 'TownTest', 'spawn_xy_m': [0., 0.],
                     'left_turn_route_waypoint_ids': [1, 2],
                     'ego_blueprint_id': 'vehicle.test',
                     'controller_policy': {'target_speed_mps': 5.0}}
        self.adapter = NativeCarlaAdapter(self.world, carla, self.packet,
                                          self.config)

    def test_exact_four_camera_frame_and_restoration(self):
        self.adapter.start(self.plan)
        self.assertTrue(self.world.settings.synchronous_mode)
        frame = self.adapter.tick()['frame']
        self.assertEqual(self.world.ego.controls[-1].throttle, .35)
        ego = self.adapter.read_ego(frame)
        body = self.adapter.read_body(frame)
        cameras = self.adapter.read_cameras(frame)
        self.assertEqual(ego['ego_body_vertices_xy_m'],
                         [v[:2] for v in body['body_vertices_m']])
        self.assertEqual(set(cameras), set(self.packet['camera_transforms']))
        self.assertTrue(all(row['png'].startswith(b'\x89PNG') for row in cameras.values()))
        self.assertEqual(self.adapter.read_road_geometry(), self.packet['road_geometry'])
        self.adapter.brake()
        self.adapter.cleanup()
        self.assertFalse(self.world.settings.synchronous_mode)
        self.assertTrue(self.world.ego.destroyed)
        self.assertTrue(all(s.stopped and s.destroyed for s in self.world.sensors))

    def test_source_pose_and_route_mismatch_before_spawn(self):
        self.packet['spawn_transform'] = {'x': 3, 'y': 0, 'z': 1, 'yaw': 0}
        with self.assertRaisesRegex(ValueError, 'spawn differs'):
            self.adapter.start(self.plan)
        self.assertEqual(self.world.sensors, [])
        self.packet['spawn_transform']['x'] = 0
        self.packet['route_transforms'][1]['waypoint_id'] = 3
        with self.assertRaisesRegex(ValueError, 'route differs'):
            self.adapter.start(self.plan)
        self.assertFalse(self.world.settings.synchronous_mode)

    def test_lazy_original_source_launch_requires_new_output(self):
        with tempfile.TemporaryDirectory(dir='.runtime-work') as temp:
            packet = Path(temp) / 'map-packet.json'
            packet.write_text(json.dumps(self.packet))
            output = Path(temp) / 'attempt'
            client = NS(set_timeout=lambda _: None, get_world=lambda: self.world)
            carla = NS(Client=lambda host, port: client)
            with patch.object(runner, 'check', return_value={'case_id': 'exact'}), \
                 patch.object(runner, 'run_capture', return_value={'frame_count': 900}) as capture:
                result = runner.run_native_source(self.config, packet, output,
                                                  'localhost', 2000,
                                                  carla_module=carla)
                self.assertEqual(result['frame_count'], 900)
                self.assertIsInstance(capture.call_args.args[0], NativeCarlaAdapter)
                self.assertEqual(capture.call_args.args[3], output)
                output.mkdir()
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    runner.run_native_source(self.config, packet, output,
                                             'localhost', 2000,
                                             carla_module=carla)


if __name__ == '__main__':
    unittest.main()
