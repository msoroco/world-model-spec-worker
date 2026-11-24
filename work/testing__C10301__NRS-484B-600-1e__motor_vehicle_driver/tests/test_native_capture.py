import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import capture
from native_media import NativeMedia
from delivery_audit import audit_decoded_media
from saved_speed import process_delivery

CASE = ROOT.name + '__above'
CAMERAS = ('front', 'front_left', 'front_right', 'rear')


class Blueprint:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Actor:
    def __init__(self):
        self.speed = 0.0
        self.x = 0.0
        self.control = SimpleNamespace(throttle=0.0, brake=0.0)
        self.destroyed = False

    def get_velocity(self):
        return SimpleNamespace(x=self.speed, y=0.0, z=0.0)

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=0.0, z=0.0))

    def apply_control(self, control):
        self.control = control

    def destroy(self):
        self.destroyed = True


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True

    def emit(self, frame):
        if self.callback:
            self.callback(SimpleNamespace(frame=frame, width=4, height=4,
                            raw_data=bytes([0, 0, 0, 255] * 16)))


class Map:
    name = 'diagnostic-map'

    def to_opendrive(self):
        return '<OpenDRIVE diagnostic="true"/>'

    def get_waypoint(self, location):
        return SimpleNamespace(road_id=1, lane_id=-1,
                               transform=SimpleNamespace(location=location))


class World:
    def __init__(self, *, miss_camera_at=None):
        self.map = Map()
        self.actor = None
        self.sensors = []
        self.frame = 100
        self.elapsed = 0.0
        self.miss_camera_at = miss_camera_at

    def get_map(self):
        return self.map

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: Blueprint(name))

    def spawn_actor(self, blueprint, transform, attach_to=None):
        if blueprint.name.startswith('vehicle.'):
            self.actor = Actor()
            return self.actor
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor

    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)

    def tick(self):
        self.actor.speed = max(0.0, self.actor.speed +
                               0.25 * self.actor.control.throttle -
                               0.5 * self.actor.control.brake)
        self.actor.x += self.actor.speed * 0.05
        self.frame += 1
        self.elapsed += 0.05
        for index, sensor in enumerate(self.sensors):
            if not (self.frame == self.miss_camera_at and index == 3):
                sensor.emit(self.frame)
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
               timestamp=SimpleNamespace(elapsed_seconds=self.elapsed))


def transform(spec):
    return SimpleNamespace(location=SimpleNamespace(x=spec.get('x_m', 0),
                           y=spec.get('y_m', 0), z=spec.get('z_m', 0)))


def control(**kwargs):
    return SimpleNamespace(**kwargs)


def media_factory(sensors, attempt, *, diagnostic_fixture):
    return NativeMedia(sensors, attempt, diagnostic_fixture=diagnostic_fixture,
                       dimensions={name: (4, 4) for name in CAMERAS},
                       timeout_s=0.2)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempt = self.root / 'attempt'
        self.site = self.root / 'site.json'
        self.world = World()
        packet = {'format': 'c10301-native-site-v1', 'case_id': CASE,
                  'cell_id': 'C10301', 'layout': 'alley',
                  'control': 'access_aisle', 'actor': 'motor_vehicle_driver',
                  'maneuver': 'travel', 'diagnostic_fixture': True,
                  'map_name': self.world.map.name,
                  'opendrive_sha256': hashlib.sha256(
                      self.world.map.to_opendrive().encode()).hexdigest(),
                  'access_aisle_source_ref': 'diagnostic aisle',
                  'route_source_ref': 'diagnostic route',
                  'route': [{'s_m': 10 * i, 'x_m': 10 * i,
                             'y_m': 0, 'z_m': 0} for i in range(181)],
                  'vehicle_blueprint_id': 'vehicle.diagnostic',
                  'cameras': {name: {'blueprint_id': 'sensor.camera.rgb',
                                     'x_m': 0, 'y_m': 0, 'z_m': 1.5,
                                     'pitch_deg': 0, 'yaw_deg': 0,
                                     'roll_deg': 0} for name in CAMERAS}}
        self.site.write_text(json.dumps(packet) + '\n')

    def test_full_diagnostic_capture_is_source_joined_and_decodable(self):
        receipt = capture(self.world, self.site, self.attempt, CASE, 'run-1',
                          0.05, transform, control, diagnostic_fixture=True,
                          media_factory=media_factory)
        self.assertEqual(receipt['motion']['sample_count'], 900)
        self.assertEqual(receipt['capture_index']['frame_count'], 900)
        self.assertEqual(receipt['capture_index']['native_site']['sha256'],
                         receipt['site_packet_sha256'])
        authored = json.loads((self.attempt / 'authored-setup.json').read_text())
        self.assertEqual(authored['requested_speed_mph'], 85.0)
        self.assertEqual(authored['native_site_sha256'], receipt['site_packet_sha256'])
        decoded = audit_decoded_media(self.attempt, CASE,
                                      allow_diagnostic=True)
        self.assertTrue(decoded['full_video_decode'])
        self.assertFalse(decoded['physical_completion'])
        saved = process_delivery(self.attempt, CASE, self.root / 'saved.json',
                                 allow_diagnostic=True)
        self.assertEqual(saved['native_run_id'], 'run-1')
        self.assertTrue(saved['media_audit']['full_video_decode'])
        route_path = self.attempt / 'route-frame-readback.json'
        self.assertTrue(route_path.is_file())
        self.assertEqual(len(json.loads(route_path.read_text())['frames']), 900)
        original_route = route_path.read_bytes()
        route_path.write_bytes(original_route + b'changed')
        with self.assertRaisesRegex(ValueError, 'original route readback hash differs'):
            audit_decoded_media(self.attempt, CASE, allow_diagnostic=True)
        route_path.write_bytes(original_route)
        route = json.loads(original_route)
        route['frames'][400]['centerline_offset_m'] = 3.0
        route_path.write_text(json.dumps(route) + '\n')
        motion_path = self.attempt / 'native-motion-receipt.json'
        original_motion = motion_path.read_bytes()
        motion = json.loads(original_motion)
        motion['route_frame_readback_sha256'] = hashlib.sha256(route_path.read_bytes()).hexdigest()
        motion_path.write_text(json.dumps(motion) + '\n')
        index_path = self.attempt / 'capture-index.json'
        original_index = index_path.read_bytes()
        index = json.loads(original_index)
        index['native_motion']['sha256'] = hashlib.sha256(motion_path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index) + '\n')
        with self.assertRaisesRegex(ValueError, 'left reviewed lane or centerline'):
            audit_decoded_media(self.attempt, CASE, allow_diagnostic=True)
        route_path.write_bytes(original_route)
        motion_path.write_bytes(original_motion)
        index_path.write_bytes(original_index)
        self.assertTrue(self.world.actor.destroyed)
        self.assertTrue(all(sensor.destroyed and sensor.stopped
                            for sensor in self.world.sensors))
        (self.attempt / 'native-site-source.json').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Native site source hash differs'):
            audit_decoded_media(self.attempt, CASE, allow_diagnostic=True)

    def test_missing_native_camera_frame_stops_and_cleans_up(self):
        self.world.miss_camera_at = 103
        with self.assertRaisesRegex(ValueError, 'original Native frame missing'):
            capture(self.world, self.site, self.attempt, CASE, 'run-2',
                    0.05, transform, control, diagnostic_fixture=True,
                    media_factory=media_factory)
        self.assertTrue(self.world.actor.destroyed)
        self.assertEqual(self.world.actor.control.brake, 1.0)
        self.assertTrue(all(sensor.destroyed and sensor.stopped
                            for sensor in self.world.sensors))
        self.assertFalse((self.attempt / 'capture-index.json').exists())


if __name__ == '__main__':
    unittest.main()
