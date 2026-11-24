import hashlib
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carla_live_adapter import CarlaTickAdapter, WorldLease
from test_native_source_review import Map
from test_native_acquisition import waypoint


def obj(**values):
    return types.SimpleNamespace(**values)


class Vehicle:
    def __init__(self, identifier):
        self.id = identifier
        self.bounding_box = obj(get_world_vertices=lambda _: [obj(x=0.0, y=0.0, z=0.0)] * 8)
        self.destroyed = False

    def get_transform(self):
        return obj(get_forward_vector=lambda: obj(x=0.0, y=1.0))

    def get_velocity(self):
        return obj(length=lambda: 0.0)

    def get_control(self):
        return obj(throttle=0.0, brake=1.0, steer=0.0)

    def get_light_state(self):
        return 1

    def destroy(self):
        self.destroyed = True


class Sensor:
    def listen(self, callback):
        self.callback = callback


class World:
    def __init__(self):
        self.map = Map()
        self.settings = obj(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = obj(name='original')
        self.sensors = [Sensor() for _ in range(4)]
        self.frame = 0
        self.bad_frame = False

    def get_map(self):
        return self.map

    def get_settings(self):
        return obj(**vars(self.settings))

    def apply_settings(self, value):
        self.settings = value

    def get_weather(self):
        return self.weather

    def set_weather(self, value):
        self.weather = value

    def tick(self):
        self.frame += 1
        for sensor in self.sensors:
            sensor.callback(obj(frame=self.frame + int(self.bad_frame), width=2, height=2,
                                raw_data=bytes([10, 20, 30, 255] * 4)))
        return self.frame

    def get_snapshot(self):
        return obj(frame=self.frame, timestamp=obj(elapsed_seconds=self.frame / 20))


class LiveAdapter(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.ego, self.other = Vehicle(11), Vehicle(12)
        self.packet = {'map_sha256': hashlib.sha256(self.world.map.road.encode()).hexdigest(),
                       'source_ref': 'fake-live-survey', 'junction_id': 9,
                       'intersection_polygon': [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                       'ego_route': [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
                       'opposing_route': [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
                       'ego_blueprint_id': 'vehicle.ego', 'opponent_blueprint_id': 'vehicle.other',
                       'reviewed_original_map': True}

    def adapter(self):
        return CarlaTickAdapter(world=self.world, packet=self.packet,
                                ego=self.ego, opponent=self.other,
                                cameras=dict(zip(('overview', 'approach', 'reference_corner', 'driver_reference'),
                                                 self.world.sensors)),
                                control_step=lambda ego, other: None,
                                location_factory=lambda x, y: (x, y), left_blinker_mask=1)

    def test_live_callback_sample_is_source_bound(self):
        adapter = self.adapter()
        frame, time_s, sample, pixels = adapter.tick()
        self.assertEqual((frame, time_s), (1, 0.05))
        self.assertEqual((sample['ego_actor_id'], sample['opponent_actor_id']), (11, 12))
        self.assertTrue(sample['ego_signal_left'])
        self.assertEqual(len(pixels), 4)
        self.assertTrue(all(data.startswith(b'\x89PNG') for data in pixels.values()))
        self.assertEqual(adapter.source_attestation()['native_origin'], True)

    def test_wrong_frame_fails(self):
        adapter = self.adapter()
        self.world.bad_frame = True
        with self.assertRaisesRegex(ValueError, 'callback frame mismatch'):
            adapter.tick()

    def test_world_lease_restores_and_destroys_on_error(self):
        original = self.world.get_settings()
        with self.assertRaisesRegex(RuntimeError, 'stop'):
            with WorldLease(self.world) as lease:
                self.assertTrue(self.world.settings.synchronous_mode)
                lease.own(self.ego)
                raise RuntimeError('stop')
        self.assertTrue(self.ego.destroyed)
        self.assertEqual(vars(self.world.settings), vars(original))


if __name__ == '__main__':
    unittest.main()
