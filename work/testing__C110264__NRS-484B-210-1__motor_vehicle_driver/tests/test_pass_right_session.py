"""Source and world-lifecycle checks for the operator Native session."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pass_right_session as session
from test_pass_right_actor import packet as source_packet


class Actor:
    def __init__(self, actor_id):
        self.id = actor_id
        self.is_alive = True
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.settings = N(synchronous_mode=False, fixed_delta_seconds=None)
        self.applied = []

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings
        self.applied.append((settings.synchronous_mode,
                             settings.fixed_delta_seconds))


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        self.source = b'original-opendrive-text'
        packet = source_packet()
        packet.update(public_highway_observed=True, two_way_observed=True)
        self.packet = self.root / 'map.json'
        self.packet.write_text(json.dumps(packet) + '\n')
        self.packet_sha = hashlib.sha256(self.packet.read_bytes()).hexdigest()
        self.ego, self.target = Actor(7), Actor(8)
        self.sensors = {name: Actor(i + 20) for i, name in
                        enumerate(('front', 'rear', 'left', 'right'))}

    def run_case(self, map_reader=None, sensors=None):
        return session.run_session(
            self.world, packet_path=self.packet, packet_sha256=self.packet_sha,
            variant='left_signal', attempt=self.root / 'attempt',
            map_reader=map_reader or (lambda world: self.source),
            spawn_actors=lambda *args: (self.ego, self.target),
            spawn_sensors=lambda *args: self.sensors if sensors is None else sensors,
            controller_factory=lambda *args: lambda frame: None,
            frame_map=object(), left_signal_mask=0x20)

    @mock.patch.object(session, 'capture_native_attempt')
    def test_capture_receipt_and_world_restoration(self, capture):
        capture.return_value = {'trace': {'source_kind': 'original_native_actor_trace'},
                                'cameras': {'front': {'sha256': 'a'}},
                                'diagnostic_profile': False}
        receipt = self.run_case()
        self.assertEqual(self.world.applied, [(True, .05), (False, None)])
        self.assertEqual(receipt['map_sha256'], hashlib.sha256(self.source).hexdigest())
        self.assertEqual(receipt['trace_sha256'], hashlib.sha256(
            (self.root / 'attempt' / 'trace.json').read_bytes()).hexdigest())
        self.assertTrue(all(a.destroyed for a in
                            [self.ego, self.target, *self.sensors.values()]))
        self.assertTrue(callable(capture.call_args.kwargs['before_tick']))

    def test_wrong_loaded_map_fails_before_mutation(self):
        with self.assertRaisesRegex(ValueError, 'loaded original map'):
            self.run_case(map_reader=lambda world: b'other OpenDRIVE')
        self.assertEqual(self.world.applied, [])

    @mock.patch.object(session, 'capture_native_attempt', side_effect=ValueError('camera gap'))
    def test_capture_error_restores_world_and_destroys_actors(self, capture):
        with self.assertRaisesRegex(ValueError, 'camera gap'):
            self.run_case()
        self.assertEqual(self.world.applied[-1], (False, None))
        self.assertTrue(all(a.destroyed for a in
                            [self.ego, self.target, *self.sensors.values()]))

    def test_missing_camera_rejects_and_restores(self):
        with self.assertRaisesRegex(ValueError, 'four original camera'):
            self.run_case(sensors={'front': self.sensors['front']})
        self.assertEqual(self.world.applied[-1], (False, None))
        self.assertTrue(self.ego.destroyed and self.target.destroyed)

    def test_clock_readback_refusal_restores(self):
        def refused(settings):
            if settings.synchronous_mode:
                self.world.applied.append((True, settings.fixed_delta_seconds))
            else:
                self.world.settings = settings
                self.world.applied.append((False, None))
        self.world.apply_settings = refused
        with self.assertRaisesRegex(ValueError, 'clock readback'):
            self.run_case()
        self.assertEqual(self.world.applied[-1], (False, None))
