"""Exercise owned Native site and world lifecycle without CARLA."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from owned_capture import capture_owned


CASE = 'testing__C110454__NRS-484D-165-4__motor_vehicle_driver__low_beam'


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class Blueprint:
    def __init__(self):
        self.attrs = {}

    def set_attribute(self, key, value):
        self.attrs[key] = value


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=.1)
        self.weather = SimpleNamespace(cloudiness=0.0)
        self.native_map = SimpleNamespace(name='TestTown', to_opendrive=lambda: '<road/>')
        self.actors = []
        self.blueprints = []

    def get_map(self): return self.native_map
    def get_settings(self): return self.settings
    def apply_settings(self, value): self.settings = value
    def get_weather(self): return self.weather
    def set_weather(self, value): self.weather = value
    def get_blueprint_library(self): return SimpleNamespace(find=self.find)

    def find(self, name):
        result = Blueprint()
        self.blueprints.append((name, result))
        return result

    def spawn_actor(self, blueprint, transform, attach_to=None):
        result = Actor()
        self.actors.append(result)
        return result


class Client:
    def __init__(self): self.world = World()
    def get_world(self): return self.world
    def get_available_maps(self): return ['TestTown']
    def load_world(self, name): return self.world


class OwnedCaptureTests(unittest.TestCase):
    def packet(self, root):
        path = root / 'site.json'
        path.write_text(json.dumps({
            'format': 'parked-headlamp-site-v1', 'case_id': CASE,
            'cell_id': 'C110454', 'actor': 'motor_vehicle_driver',
            'diagnostic_fixture': True,
            'parking_source_ref': 'diagnostic-parking',
            'intersection_source_ref': 'diagnostic-intersection',
            'map_name': 'TestTown',
            'map_sha256': hashlib.sha256(b'<road/>').hexdigest(),
            'parking_polygon_xy_m': [[0, 0], [1, 0], [1, 1], [0, 1]],
            'intersection_polygon_xy_m': [[2, 2], [3, 2], [3, 3], [2, 3]],
            'vehicle_blueprint_id': 'vehicle.test',
            'vehicle_transform': {'x_m': 0, 'y_m': 0, 'z_m': 0},
            'cameras': {v: {'blueprint_id': 'sensor.camera.rgb'}
                        for v in ('overview', 'approach', 'reference_corner', 'driver_reference')},
        }) + '\n')
        return path

    def test_success_seals_receipt_and_restores_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = Client()
            packet = self.packet(root)
            expected = {'format': 'parked-headlamp-native-source-v1'}
            with patch('owned_capture.capture_interval', return_value=expected) as capture:
                result = capture_owned(client, packet, root / 'attempt', case_id=CASE,
                    mode='low_beam', transform_factory=lambda value: value,
                    control_factory=lambda **kw: SimpleNamespace(**kw),
                    light_enum=object(), recorder_factory=lambda *args: object(),
                    diagnostic_fixture=True)
            self.assertEqual(result, expected)
            self.assertEqual(json.loads((root / 'attempt/native-source-receipt.json').read_text()), expected)
            self.assertEqual(len(client.world.actors), 5)
            self.assertTrue(all(actor.destroyed for actor in client.world.actors))
            self.assertFalse(client.world.settings.synchronous_mode)
            self.assertEqual(capture.call_args.args[5]['source_sha256'],
                             hashlib.sha256(packet.read_bytes()).hexdigest())
            self.assertEqual(client.world.blueprints[1][1].attrs['sensor_tick'], '0.05')

    def test_failed_capture_cleans_actors_and_restores_world(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = Client()
            with patch('owned_capture.capture_interval', side_effect=ValueError('missing camera')):
                with self.assertRaisesRegex(ValueError, 'missing camera'):
                    capture_owned(client, self.packet(root), root / 'attempt', case_id=CASE,
                        mode='low_beam', transform_factory=lambda value: value,
                        control_factory=lambda **kw: SimpleNamespace(**kw),
                        light_enum=object(), recorder_factory=lambda *args: object(),
                        diagnostic_fixture=True)
            self.assertTrue(all(actor.destroyed for actor in client.world.actors))
            self.assertFalse(client.world.settings.synchronous_mode)
            self.assertFalse((root / 'attempt/native-source-receipt.json').exists())


if __name__ == '__main__': unittest.main()
