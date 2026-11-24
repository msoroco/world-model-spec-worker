import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from live_capture import run
from test_carla_live_adapter import Vehicle, World, obj
from test_native_acquisition import waypoint
from saved_left_turn import ASSIGNMENT_ID


class OpposingVehicle(Vehicle):
    def get_transform(self):
        return obj(get_forward_vector=lambda: obj(x=0.0, y=-1.0))


def packet(world):
    return {'map_sha256': hashlib.sha256(world.map.road.encode()).hexdigest(),
            'source_ref': 'reviewed-live-survey', 'junction_id': 9,
            'intersection_polygon': [[-5, -5], [5, -5], [5, 5], [-5, 5]],
            'ego_route': [waypoint(0, -10, None), waypoint(0, 0, 9),
                          waypoint(-10, 0, None)],
            'opposing_route': [waypoint(0, 10, None), waypoint(0, 0, 9),
                               waypoint(0, -10, None)],
            'ego_blueprint_id': 'vehicle.ego',
            'opponent_blueprint_id': 'vehicle.other',
            'reviewed_original_map': True}


def config():
    return {'law_id': 'NRS-484B-253', 'cell_id': 'C109749',
            'actor': 'motor_vehicle_driver',
            'selected_case_id': ASSIGNMENT_ID + '__inside_yield',
            'rate_hz': 20, 'duration_s': 45,
            'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
            'controller': {'wait_for_initial_opponent': True,
                           'signal_left': True, 'wait_for_later_opponent': None,
                           'target_speed_mps': 5.0}}


class LiveCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.world = World()
        self.client = obj(get_world=lambda: self.world)
        self.map_path = self.root / 'map.json'
        self.config_path = self.root / 'config.json'
        self.map_path.write_text(json.dumps(packet(self.world)) + '\n', encoding='utf-8')
        self.config_path.write_text(json.dumps(config()) + '\n', encoding='utf-8')
        self.owned = []

    def tearDown(self):
        self.temp.cleanup()

    def scene(self, *, world, request, packet, lease):
        ego = lease.own(Vehicle(11))
        opponent = lease.own(OpposingVehicle(12))
        for sensor in world.sensors:
            sensor.destroy = lambda: None
        cameras = dict(zip(config()['cameras'],
                           [lease.own(sensor) for sensor in world.sensors]))
        self.owned = [ego, opponent, *cameras.values()]
        return {'ego': ego, 'opponent': opponent, 'cameras': cameras,
                'control_step': lambda ego, opponent: None}

    def call(self, **changes):
        arguments = dict(client=self.client, config_path=self.config_path,
                         map_path=self.map_path, output=self.root / 'attempt',
                         scene_factory=self.scene,
                         location_factory=lambda x, y: (x, y),
                         left_blinker_mask=1, frame_count=900)
        arguments.update(changes)
        return run(**arguments)

    def test_seals_full_live_attempt_and_restores_world(self):
        original = vars(self.world.get_settings()).copy()
        result = self.call()
        self.assertEqual(result['case_id'], config()['selected_case_id'])
        self.assertEqual(result['physical_acceptance'], 'unverified')
        self.assertEqual(vars(self.world.get_settings()), original)
        self.assertTrue(all(actor.destroyed for actor in self.owned[:2]))
        receipt = json.loads(result['files']['receipt_path'].read_text())
        self.assertFalse(receipt['diagnostic_fixture'])
        self.assertEqual(receipt['frame_count'], 900)
        self.assertEqual(len(list((self.root / 'attempt' / 'original-frames').iterdir())), 3600)

    def test_camera_failure_restores_owned_scene(self):
        self.world.bad_frame = True
        original = vars(self.world.get_settings()).copy()
        with self.assertRaisesRegex(ValueError, 'callback frame mismatch'):
            self.call()
        self.assertEqual(vars(self.world.get_settings()), original)
        self.assertTrue(all(actor.destroyed for actor in self.owned[:2]))

    def test_rejects_diagnostic_packet_before_scene_creation(self):
        source = packet(self.world)
        source['diagnostic_fixture'] = True
        self.map_path.write_text(json.dumps(source) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'reviewed original'):
            self.call()
        self.assertEqual(self.owned, [])

    def test_partial_scene_spawn_failure_restores_owned_actor(self):
        actor = Vehicle(99)

        def fail_scene(*, world, request, packet, lease):
            lease.own(actor)
            raise RuntimeError('spawn failure')

        original = vars(self.world.get_settings()).copy()
        with self.assertRaisesRegex(RuntimeError, 'spawn failure'):
            self.call(scene_factory=fail_scene)
        self.assertTrue(actor.destroyed)
        self.assertEqual(vars(self.world.get_settings()), original)


if __name__ == '__main__':
    unittest.main()
