import copy
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from native_owner_adapter import NativeOwner


class Actor:
    def __init__(self, actor_id=1, type_id='vehicle.test'):
        self.id, self.type_id = actor_id, type_id
        self.is_alive = True
        self.callback = None

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        pass

    def destroy(self):
        self.is_alive = False

    def get_state(self):
        return 'TrafficLightState.Red'

    def get_transform(self):
        return types.SimpleNamespace(
            location=types.SimpleNamespace(x=0, y=0),
            get_forward_vector=lambda: types.SimpleNamespace(x=1, y=0))

    def get_location(self):
        return types.SimpleNamespace(x=2, y=0)


class World:
    def __init__(self):
        self.settings = types.SimpleNamespace(synchronous_mode=False,
                                              fixed_delta_seconds=None)
        self.ego = Actor()
        self.sensors = []

    def get_map(self):
        return types.SimpleNamespace(name='site')

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, settings):
        self.settings = copy.copy(settings)

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda name: types.SimpleNamespace(
            id=name, set_attribute=lambda *_: None))

    def try_spawn_actor(self, *_):
        return self.ego

    def spawn_actor(self, *_):
        sensor = Actor(len(self.sensors) + 10, 'sensor.camera.rgb')
        self.sensors.append(sensor)
        return sensor

    def get_actor(self, actor_id):
        return Actor(actor_id, 'traffic.traffic_light')


class Capture:
    def __init__(self, client, ego, root, case_id):
        self.rows = []
        self.closed = False

    def capture(self, frame, time_s):
        self.rows.append((frame, time_s))

    def close(self):
        self.closed = True


class OwnerTests(unittest.TestCase):
    def context(self):
        pose = [0, 0, 1, 0, 0, 0]
        return {'native_setup': {
            'source': 'reviewed site record', 'reviewed': True,
            'ego_blueprint': 'vehicle.test', 'ego_pose': pose,
            'signals': {
                'approach_signal': {'actor_id': 31, 'red_aspect': 'red_alone'},
                'destination_signal': {'actor_id': 32, 'red_aspect': 'unknown'}},
            'cameras': {name: {'pose': pose,
                               'width': 1920 if name == 'overview' else 1280,
                               'height': 1080 if name == 'overview' else 720,
                               'fov_deg': 90} for name in
                        ('overview', 'approach', 'reference_corner', 'driver_reference')}}}

    def test_original_owner_joins_camera_signal_graph_and_restores(self):
        world = World()
        client = types.SimpleNamespace(get_world=lambda: world,
                                       set_timeout=lambda _: None)
        carla = types.SimpleNamespace(
            Client=lambda *_: client,
            Location=lambda **kwargs: types.SimpleNamespace(**kwargs),
            Rotation=lambda **kwargs: types.SimpleNamespace(**kwargs),
            Transform=lambda location, rotation: (location, rotation))
        with tempfile.TemporaryDirectory() as temp:
            owner = NativeOwner('localhost', 2000,
                {'native_map': {'map_name': 'site'}}, 'exact-case',
                Path(temp), self.context(), carla_module=carla,
                capture_class=Capture)
            with owner:
                self.assertTrue(world.settings.synchronous_mode)
                self.assertEqual(owner.signal_observer(7, 'approach_signal')['state'],
                                 'red_alone')
                self.assertEqual(owner.signal_observer(7, 'destination_signal')['state'],
                                 'unknown')
                owner.graph_observer(7, .35)
                raw = bytes([0, 0, 255, 255]) * (1920 * 1080)
                world.sensors[0].callback(types.SimpleNamespace(
                    raw_data=raw, width=1920, height=1080, frame=7))
                with Image.open(io.BytesIO(owner.camera_observer(7, 'overview'))) as image:
                    self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))
            self.assertEqual(owner.graph.rows, [(7, .35)])
            self.assertTrue(owner.graph.closed)
            self.assertFalse(world.settings.synchronous_mode)
            self.assertTrue(owner.release_receipt()['readback_passed'])

    def test_missing_reviewed_native_setup_fails_before_connection(self):
        carla = types.SimpleNamespace(Client=lambda *_: self.fail('connected'))
        with tempfile.TemporaryDirectory() as temp:
            owner = NativeOwner('localhost', 2000,
                {'native_map': {'map_name': 'site'}}, 'exact-case',
                Path(temp), {'native_setup': {}}, carla_module=carla,
                capture_class=Capture)
            with self.assertRaisesRegex(ValueError, 'separately reviewed'):
                owner.__enter__()

    def test_camera_profile_change_is_rejected_before_capture(self):
        context = self.context()
        context['native_setup']['cameras']['overview']['width'] = 1280
        world = World()
        client = types.SimpleNamespace(get_world=lambda: world,
                                       set_timeout=lambda _: None)
        carla = types.SimpleNamespace(
            Client=lambda *_: client,
            Location=lambda **kwargs: types.SimpleNamespace(**kwargs),
            Rotation=lambda **kwargs: types.SimpleNamespace(**kwargs),
            Transform=lambda location, rotation: (location, rotation))
        with tempfile.TemporaryDirectory() as temp:
            owner = NativeOwner('localhost', 2000,
                {'native_map': {'map_name': 'site'}}, 'exact-case',
                Path(temp), context, carla_module=carla,
                capture_class=Capture)
            with self.assertRaisesRegex(ValueError, 'selected profile'):
                owner.__enter__()
            self.assertFalse(world.settings.synchronous_mode)


if __name__ == '__main__':
    unittest.main()
