"""Fake CARLA CPU proof for the source-bound Native lifecycle."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_adapter
import runner
from stand import SourceError, construct_case
from stand_capture import capture
from stand_converter_source import audit as audit_converter


class Location:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Rotation:
    def __init__(self, pitch=0, yaw=0, roll=0):
        self.pitch, self.yaw, self.roll = pitch, yaw, roll


class Transform:
    def __init__(self, location, rotation=None):
        self.location = location
        self.rotation = rotation or Rotation()


class Blueprint:
    def __init__(self, name):
        self.id = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class BlueprintLibrary:
    def find(self, name):
        return Blueprint(name)


class Actor:
    def __init__(self, actor_id, kind, location=None):
        self.id, self.type_id = actor_id, kind
        self.transform = Transform(location or Location())
        self.velocity = Location()
        self.controls = []
        self.destroyed = False
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda tr: [
            Location(0, 0), Location(4, 0), Location(4, 5), Location(0, 5)])

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return self.velocity

    def apply_control(self, control):
        self.controls.append(control)
        if hasattr(control, 'throttle'):
            self.velocity = Location(x=control.throttle)
        else:
            self.velocity = Location(x=control.speed)

    def destroy(self):
        self.destroyed = True


class Sensor(Actor):
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True


class Mapping:
    name = 'NativeTestTown'

    def get_waypoint(self, location, project_to_road=True):
        return SimpleNamespace(transform=Transform(location))

    def get_crosswalks(self):
        return []

    def to_opendrive(self):
        return '<OpenDRIVE>original-fake-world-readback</OpenDRIVE>\n'


class World:
    def __init__(self):
        self.mapping = Mapping()
        self.settings = SimpleNamespace(synchronous_mode=False,
                                        fixed_delta_seconds=None,
                                        no_rendering_mode=False)
        self.registry = {1: Actor(1, 'static.prop.sign'),
                         2: Actor(2, 'static.prop.curb')}
        self.next_id = 10
        self.sensors = []
        self.frame = 99
        self.time_s = -0.05
        self.apply_count = 0

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, settings):
        self.settings = copy.copy(settings)
        self.apply_count += 1

    def get_map(self):
        return self.mapping

    def get_actors(self):
        return SimpleNamespace(find=lambda actor_id: self.registry.get(actor_id))

    def get_blueprint_library(self):
        return BlueprintLibrary()

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(self.next_id, blueprint.id, transform.location)
        self.registry[actor.id] = actor
        self.next_id += 1
        return actor

    def spawn_actor(self, blueprint, transform):
        sensor = Sensor(self.next_id, blueprint.id, transform.location)
        self.registry[sensor.id] = sensor
        self.next_id += 1
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        self.time_s = round(self.time_s + .05, 6)
        for actor in self.registry.values():
            if actor.type_id.startswith(('vehicle.', 'walker.')):
                actor.transform.location.x += actor.velocity.x * .05
        for sensor in self.sensors:
            sensor.callback(SimpleNamespace(frame=self.frame,
                                            timestamp=self.time_s,
                                            raw_data=b'fake-native-rgb'))
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=self.time_s))


class Client:
    def __init__(self, world):
        self.world = world

    def set_timeout(self, seconds):
        self.timeout = seconds

    def get_world(self):
        return self.world

    def get_server_version(self):
        return 'fake-carla-unit-test'


class Encoder:
    def __init__(self, path, width, height):
        self.path = path
        self.count = 0

    def feed(self, raw):
        self.count += 1

    def finish(self):
        if self.count != 900:
            raise SourceError('fake RGB frames incomplete')
        self.path.write_bytes(b'fake-native-rgb-unit-test')

    def abort(self):
        self.aborted = True


def native_site():
    poses = {name: {'location_m': [10, 10, 2], 'rotation_deg': [0, 0, 0]}
             for name in native_adapter.VIEWS}
    return {'kind': 'taxicab_stand', 'cell_id': 'C135087',
            'highway_status_source': 'unit-test-only',
            'designation_source': 'unit-test-only',
            'sign_source': 'unit-test-only', 'map_name': 'NativeTestTown',
            'lane_id': 1, 'curb_polygon': [[0, 0], [4, 0], [4, 5], [0, 5]],
            'approach_lane_id': 2, 'access_waypoints': [[0, -10], [0, 0]],
            'stand_waypoint': [1, 1], 'passenger_waypoint': [2, 1],
            'sign_id': 'test-sign',
            'native_binding': {
                'sign_actor_id': 1, 'sign_blueprint': 'static.prop.sign',
                'curb_actor_id': 2, 'curb_blueprint': 'static.prop.curb',
                'passenger_blueprint': 'walker.test', 'camera_transforms': poses,
                'access_polygon': [[0, 0], [4, 0], [4, 5], [0, 5]],
                'observation': {'loading_radius_m': 3,
                                'entry_range_m': 15, 'motion_epsilon_mps': .01},
                'control': {'approach_frames': 20, 'loading_frames': 100,
                            'entrant_start_frame': 5, 'subject_throttle': .2,
                            'passenger_speed_mps': .1, 'entrant_throttle': .1}}}


def vehicles():
    return {'subject': {'kind': 'passenger_vehicle',
                        'compensated_taxicab_use': False,
                        'driver_identity_source': 'unit-test-only',
                        'blueprint': 'vehicle.test'},
            'entrant': {'kind': 'motor_vehicle',
                        'design_capacity_including_driver': 5,
                        'compensated_passenger_use_source': 'unit-test-only',
                        'blueprint': 'vehicle.taxi'}}


class NativeAdapterTests(unittest.TestCase):
    def test_lazy_import_and_unreviewed_source_rejected_before_world(self):
        with patch.object(runner.importlib, 'import_module') as imported:
            with self.assertRaisesRegex(SourceError, 'reviewed original stand'):
                runner.run(None, None, None, None)
            imported.assert_not_called()
        site = native_site()
        del site['native_binding']
        with self.assertRaisesRegex(SourceError, 'reviewed Native stand binding missing'):
            native_adapter.validate_native_sources(site, vehicles())

    def test_encoder_abort_and_world_restoration_after_capture_failure(self):
        world = World()
        carla = SimpleNamespace(Location=Location, Rotation=Rotation,
                                Transform=Transform, Vector3D=Location,
                                VehicleControl=lambda **kw: SimpleNamespace(**kw),
                                WalkerControl=lambda **kw: SimpleNamespace(**kw))
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work'
        with tempfile.TemporaryDirectory(dir=scratch, prefix='c135087-native-abort-') as temp:
            root = Path(temp)
            site, roles = native_site(), vehicles()
            import hashlib
            refs = []
            for name, value in (('site', site), ('vehicle', roles)):
                path = root / (name + '.json')
                path.write_text(json.dumps(value) + '\n')
                refs.append({'path': str(path),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            session = native_adapter.open_session('localhost', 2000, {}, carla_module=carla,
                    client_factory=lambda host, port: Client(world), encoder_factory=Encoder)
            with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                with session:
                    constructed = construct_case(session.adapter, refs[0], refs[1],
                        {'case_id': 'test', 'loading_mode': 'active',
                         'entrant_mode': 'about_to_enter', 'access_mode': 'open'})
                    session.start_cameras(root, [{'name': name, 'width': 4, 'height': 4,
                                                   'fov_deg': 90} for name in native_adapter.VIEWS],
                                          constructed)
                    raise RuntimeError('capture failed')
            self.assertTrue(session.restoration_verified)
            self.assertEqual(len(session.encoders), 4)
            self.assertTrue(all(encoder.aborted for encoder in session.encoders.values()))
            self.assertTrue(all(sensor.stopped for sensor in session.sensors.values()))
            self.assertTrue(all(actor.destroyed for actor in session.owned))

    def test_900_live_frame_export_and_restoration(self):
        world = World()
        carla = SimpleNamespace(Location=Location, Rotation=Rotation,
                                Transform=Transform, Vector3D=Location,
                                VehicleControl=lambda **kw: SimpleNamespace(**kw),
                                WalkerControl=lambda **kw: SimpleNamespace(**kw))
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work'
        with tempfile.TemporaryDirectory(dir=scratch, prefix='c135087-native-unit-') as temp:
            root = Path(temp)
            site, roles = native_site(), vehicles()
            site_path, vehicle_path = root / 'site.json', root / 'vehicle.json'
            site_path.write_text(json.dumps(site) + '\n')
            vehicle_path.write_text(json.dumps(roles) + '\n')
            import hashlib
            site_ref = {'path': str(site_path),
                        'sha256': hashlib.sha256(site_path.read_bytes()).hexdigest()}
            vehicle_ref = {'path': str(vehicle_path),
                           'sha256': hashlib.sha256(vehicle_path.read_bytes()).hexdigest()}
            config = {'selected_case_id': 'testing__C135087__NRS-484B-517__motor_vehicle_driver__unit_test'}
            case = {'case_id': config['selected_case_id'], 'loading_mode': 'active',
                    'entrant_mode': 'about_to_enter', 'access_mode': 'open'}
            with native_adapter.open_session('localhost', 2000, config,
                    carla_module=carla, client_factory=lambda host, port: Client(world),
                    encoder_factory=Encoder) as session:
                built = construct_case(session.adapter, site_ref, vehicle_ref, case)
                cameras = [{'name': name, 'width': 4, 'height': 4, 'fov_deg': 90}
                           for name in native_adapter.VIEWS]
                session.start_cameras(root, cameras, built)
                attempt = capture(session.world, session.actors, session.observer,
                                  case['case_id'], site['map_name'], root,
                                  step=session.step, camera_finalize=session.finish_cameras)
                original_trace = (root / 'trace.jsonl').read_bytes()
                session.export_converter_sources(root, built, attempt)
                self.assertEqual((root / 'trace.jsonl').read_bytes(), original_trace)
                receipt = audit_converter(root, attempt)
                self.assertEqual(receipt['frames'], 900)
                self.assertEqual(receipt['graph_count'], 900)
                self.assertEqual([len(v) for v in session.camera_frames.values()], [900] * 4)
            self.assertTrue(session.restoration_verified)
            self.assertFalse(world.get_settings().synchronous_mode)
            self.assertTrue(all(actor.destroyed for actor in session.owned))
            self.assertTrue(all(sensor.stopped for sensor in session.sensors.values()))


if __name__ == '__main__':
    unittest.main()
