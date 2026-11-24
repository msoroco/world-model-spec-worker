"""CPU owner and exact callback tests for the lazy Native CARLA bridge."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from unittest.mock import MagicMock

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

    def get_actors(self):
        return [self.ego, *self.sensors]

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

    def test_original_recorder_lifecycle_and_actor_census(self):
        with tempfile.TemporaryDirectory(dir='.runtime-work') as temp:
            record = Path(temp) / 'carla_recorder.log'
            events = []

            def start(path, extra):
                events.append(('start', path, extra))
                record.write_bytes(b'original binary CARLA recorder')
                return 'Recorder started'

            def stop():
                events.append(('stop',))

            client = NS(start_recorder=start, stop_recorder=stop,
                        show_recorder_file_info=lambda path, verbose:
                        ' Create 7: vehicle.test at 0 0 0\n')
            self.adapter.client = client
            self.adapter.start(self.plan)
            self.adapter.start_recorder(record)
            self.assertEqual(self.adapter.stop_recorder(),
                             ' Create 7: vehicle.test at 0 0 0\n')
            self.assertEqual(events, [('start', str(record), True), ('stop',)])
            self.adapter.cleanup()

    def test_missing_recorder_census_rejected(self):
        with tempfile.TemporaryDirectory(dir='.runtime-work') as temp:
            record = Path(temp) / 'carla_recorder.log'
            client = NS(start_recorder=lambda path, extra: record.write_bytes(b'x'),
                        stop_recorder=lambda: None,
                        show_recorder_file_info=lambda path, verbose: '')
            self.adapter.client = client
            self.adapter.start(self.plan)
            self.adapter.start_recorder(record)
            with self.assertRaisesRegex(ValueError, 'actor census missing'):
                self.adapter.stop_recorder()
            self.adapter.cleanup()

    def test_original_signal_group_inventory(self):
        light = NS(id=17, type_id='traffic.traffic_light', is_alive=True,
                   get_transform=lambda: NS(location=NS(x=3., y=4., z=2.)),
                   get_light_boxes=lambda: [object(), object()],
                   get_state=lambda: 'TrafficLightState.Green')
        original_get_actors = self.world.get_actors
        self.world.get_actors = lambda: [*original_get_actors(), light]
        self.adapter.start(self.plan)
        frame = self.adapter.tick()['frame']
        observed = self.adapter.read_control_inventory(frame)
        self.assertEqual(observed['control_actor_inventory']['actor_ids'], [17])
        self.assertEqual(observed['devices'][0]['light_box_method'],
                         'TrafficLight.get_light_boxes')
        self.assertEqual(observed['devices'][0]['light_boxes'],
                         [{'light_box_index': 0}, {'light_box_index': 1}])
        self.assertEqual(observed['devices'][0]['state'], 'Green')
        self.adapter.cleanup()

    def test_exact_four_camera_frame_and_restoration(self):
        self.adapter.start(self.plan)
        self.assertTrue(self.world.settings.synchronous_mode)
        frame = self.adapter.tick()['frame']
        self.assertEqual(self.world.ego.controls[-1].throttle, .35)
        ego = self.adapter.read_ego(frame)
        body = self.adapter.read_body(frame)
        participants = self.adapter.read_participants(frame)
        controls = self.adapter.read_control_inventory(frame)
        cameras = self.adapter.read_cameras(frame)
        self.assertEqual(ego['ego_body_vertices_xy_m'],
                         [v[:2] for v in body['body_vertices_m']])
        self.assertEqual(body['velocity_mps'], [0., 0., 0.])
        self.assertEqual(body['velocity_source'],
                         'original_trace_actor_get_velocity')
        self.assertEqual([actor['actor_id'] for actor in participants], [7])
        self.assertEqual(participants[0]['body_vertices_m'],
                         body['body_vertices_m'])
        self.assertEqual(controls['devices'], [])
        self.assertEqual(controls['control_actor_inventory']['actor_ids'], [])
        self.assertTrue(controls['control_actor_inventory']['complete'])
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

    def test_publication_rejects_diagnostic_source_before_core_or_seal(self):
        with tempfile.TemporaryDirectory(dir='.runtime-work') as temp:
            root = Path(temp)
            output = root / 'materialized'
            output.mkdir()
            (output / 'construction.json').write_text('{}')
            packet_path = root / 'packet.json'
            packet_path.write_text('{}')

            def source(config, packet, path, host, port, **kwargs):
                path.mkdir()
                (path / 'acquisition.json').write_text(json.dumps({
                    'diagnostic_fixture': True, 'map_binding': {}}))
                return {'frame_count': 900, 'restoration_verified': True}

            fake_seal = MagicMock()
            fake_worker = NS(native_output=NS(seal_capture=fake_seal))
            with patch.dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(root)), \
                 patch.dict(sys.modules, {'worker_exchange': fake_worker,
                                         'worker_exchange.native_output':
                                         fake_worker.native_output}), \
                 patch.object(runner, 'run_native_source', side_effect=source), \
                 patch('native_core.project') as project:
                with self.assertRaisesRegex(ValueError, 'diagnostic source'):
                    runner.run_native_publication(self.config, packet_path,
                                                  output, 'localhost', 2000)
                project.assert_not_called()
                fake_seal.assert_not_called()
                self.assertTrue(json.loads((output / 'native-run-status.json')
                                           .read_text())['errors'])

    def test_publication_order_copies_sources_before_closure(self):
        with tempfile.TemporaryDirectory(dir='.runtime-work') as temp:
            root = Path(temp)
            output = root / 'materialized'
            output.mkdir()
            (output / 'construction.json').write_text('{}')
            packet_path = root / 'packet.json'
            packet_path.write_text('{}')

            def source(config, packet, path, host, port, **kwargs):
                path.mkdir()
                (path / 'acquisition.json').write_text(json.dumps({
                    'diagnostic_fixture': False,
                    'map_binding': {'map_name': 'TownTest'}}))
                return {'frame_count': 900, 'restoration_verified': True}

            def core(source_path, target):
                target.mkdir()
                (target / 'receipt.json').write_text('{}')
                (target / 'trace.jsonl').write_text('{}\n')
                return {'media': {'encoded_camera_sha256': {
                    name: 'hash' for name in ('overview', 'approach',
                                              'reference_corner', 'driver_reference')}}}

            def seal(path, **kwargs):
                self.assertTrue((path / 'acquisition.json').is_file())
                self.assertTrue((path / 'trace.jsonl').is_file())
                self.assertTrue((path / 'acquisition-provenance.json').is_file())
                self.assertEqual(kwargs['encoder_exit_codes'], {
                    name: 0 for name in ('overview', 'approach',
                                         'reference_corner', 'driver_reference')})
                self.assertTrue(kwargs['restoration']['restored'])
                return {'format': 'worker-sealed-capture'}

            fake_worker = NS(native_output=NS(seal_capture=seal))
            with patch.dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(root)), \
                 patch.dict(sys.modules, {'worker_exchange': fake_worker,
                                         'worker_exchange.native_output':
                                         fake_worker.native_output}), \
                 patch.object(runner, 'run_native_source', side_effect=source), \
                 patch('native_core.project', side_effect=core):
                value = runner.run_native_publication(self.config, packet_path,
                                                      output, 'localhost', 2000)
            self.assertEqual(value['capture_seal_format'], 'worker-sealed-capture')
            self.assertFalse(value['physical_acceptance_claimed'])


if __name__ == '__main__':
    unittest.main()
