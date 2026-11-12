import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from turn_native_sources import TurnSourceRecorder
from turn_signal_measurement import measure
from turn_native_route import participant_offset_xy, participant_spawn_transform

_runner_spec = importlib.util.spec_from_file_location('c111610_horn_runner', ROOT / 'runner.py')
_runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(_runner)
check_config = _runner.check_config


class Actor:
    def __init__(self, x, y, radius, yaw=0, lights=0):
        self.x, self.y, self.radius, self.yaw, self.lights = x, y, radius, yaw, lights
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=radius, y=.01))

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=self.y),
                               rotation=SimpleNamespace(yaw=self.yaw))

    def get_light_state(self):
        return self.lights


class NativeTurnSourcesTests(unittest.TestCase):
    def test_runner_accepts_bounded_pedestrian_sweep_offsets(self):
        construction = json.loads((ROOT.parent / 'native-horn-primary-construction.json').read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        config['engineering']['pedestrian_along_m'] = 6.
        config['engineering']['pedestrian_left_m'] = 14.
        self.assertEqual(check_config(config)['pedestrian_left_m'], 14.)
        for bad in (float('nan'), float('inf'), 26., True, '14'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config['engineering']['pedestrian_left_m'] = bad
                check_config(config)

    def test_runner_accepts_bounded_vehicle_sweep_offsets(self):
        construction = json.loads((ROOT.parent / 'native-horn-primary-construction.json').read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                if item['path'] == 'config.json'))
        config['engineering']['vehicle_along_m'] = 5.
        config['engineering']['vehicle_left_m'] = 5.
        self.assertEqual(check_config(config)['vehicle_left_m'], 5.)
        for bad in (float('nan'), float('inf'), 26., True, '5'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                config['engineering']['vehicle_left_m'] = bad
                check_config(config)

    def test_vehicle_sweep_uses_approach_relative_native_transform(self):
        fake_carla = SimpleNamespace(Location=lambda **fields: SimpleNamespace(**fields),
                                     Transform=lambda location, rotation: SimpleNamespace(
                                         location=location, rotation=rotation))
        for heading, near_xy, far_xy in [((1., 0.), (15., 25.), (15., 35.)),
                                         ((-1., 0.), (5., 15.), (5., 5.)),
                                         ((0., 1.), (5., 25.), (-5., 25.)),
                                         ((0., -1.), (15., 15.), (25., 15.))]:
            with self.subTest(heading=heading):
                transform = SimpleNamespace(location=SimpleNamespace(x=10., y=20., z=1.),
                                            rotation=SimpleNamespace(yaw=0.),
                                            get_forward_vector=lambda: SimpleNamespace(x=heading[0], y=heading[1]))
                waypoint = SimpleNamespace(transform=transform)
                near = participant_spawn_transform(fake_carla, waypoint, along_m=5., left_m=5.)
                far = participant_spawn_transform(fake_carla, waypoint, along_m=5., left_m=15.)
                self.assertAlmostEqual(near.location.x, near_xy[0])
                self.assertAlmostEqual(near.location.y, near_xy[1])
                self.assertAlmostEqual(far.location.x, far_xy[0])
                self.assertAlmostEqual(far.location.y, far_xy[1])
                self.assertEqual(near.location.z, 1.5)

    def test_pedestrian_sweep_geometry_follows_both_approach_headings(self):
        def waypoint(dx, dy):
            transform = SimpleNamespace(location=SimpleNamespace(x=10., y=20.),
                                        get_forward_vector=lambda: SimpleNamespace(x=dx, y=dy))
            return SimpleNamespace(transform=transform)

        for direction, expected in [((1., 0.), (16., 22.)),
                                    ((-1., 0.), (4., 18.)),
                                    ((0., 1.), (8., 26.)),
                                    ((0., -1.), (12., 14.))]:
            with self.subTest(direction=direction):
                near = participant_offset_xy(waypoint(*direction), along_m=6., left_m=2.)
                far = participant_offset_xy(waypoint(*direction), along_m=6., left_m=14.)
                self.assertAlmostEqual(near[0], expected[0])
                self.assertAlmostEqual(near[1], expected[1])
                self.assertAlmostEqual((far[0]-near[0])**2 + (far[1]-near[1])**2, 144.)
        with self.assertRaises(ValueError):
            participant_offset_xy(waypoint(1., 0.), along_m=6., left_m=float('nan'))

        fake_carla = SimpleNamespace(Location=lambda **fields: SimpleNamespace(**fields),
                                     Transform=lambda location, rotation: SimpleNamespace(
                                         location=location, rotation=rotation))
        east = waypoint(1., 0.)
        east.transform.location.z = 1.
        east.transform.rotation = SimpleNamespace(yaw=0.)
        spawned = participant_spawn_transform(fake_carla, east, along_m=6., left_m=14.)
        self.assertEqual((spawned.location.x, spawned.location.y, spawned.location.z),
                         (16., 34., 1.5))
        self.assertIs(spawned.rotation, east.transform.rotation)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ego = Actor(0, 0, 1)
        self.ped = Actor(6, 2, .3)
        self.vehicle = Actor(8, 0, 1)
        self.context = {'pedestrian_may_be_affected': False,
                        'pedestrian_may_be_affected_source': 'reviewed original pedestrian trajectory',
                        'vehicle_may_be_affected': True,
                        'vehicle_may_be_affected_source': 'reviewed original vehicle trajectory',
                        'participant_types': {'ped_1': 'pedestrian', 'vehicle_1': 'vehicle'},
                        'listener_position_source': 'original ped_1 Native transform',
                        'participant_geometry_source': 'original Native transforms and extents'}

    def recorder(self):
        return TurnSourceRecorder(self.root, self.ego,
                                  {'ped_1': self.ped, 'vehicle_1': self.vehicle},
                                  'ped_1', self.context, left_light_mask=1, right_light_mask=2)

    def packet(self, frame, samples=None):
        return {'origin': 'listener_pcm_capture', 'frame': frame, 'listener_id': 'ped_1',
                'capture_source': 'original listener PCM stream',
                'samples': [0.] * 8 if samples is None else samples}

    def test_native_readback_and_listener_samples_feed_measured_turn(self):
        recorder = self.recorder()
        for i in range(3):
            self.ego.x = i
            self.ego.yaw = 20 if i == 2 else 0
            self.ego.lights = 1 if i >= 1 else 0
            recorder.append(40 + i, i / 20, self.packet(40 + i, [.2] * 8 if i == 1 else None))
        manifest = recorder.close()
        result = measure(self.root / 'ego_turn_motion.jsonl', self.root / 'ego_signal_audio.jsonl',
                         self.root / 'affected_participants.json', self.root / 'participant_bodies.jsonl')
        self.assertEqual(result['turn_onset_frame'], 42)
        self.assertEqual(result['pre_turn_indicator_frames'], [41])
        self.assertAlmostEqual(result['max_pre_turn_listener_audio_rms'], .2)
        self.assertEqual(manifest['frames'], 3)
        self.assertIn('listener_audio_original.jsonl', manifest['sources'])
        self.assertIsNone(result['appropriate_signal_legal_judgment'])

    def test_rejects_command_only_audio_and_misaligned_listener(self):
        recorder = self.recorder()
        packet = self.packet(40)
        packet['origin'] = 'horn_command'
        with self.assertRaisesRegex(ValueError, 'command state is insufficient'):
            recorder.append(40, 0, packet)
        packet = self.packet(40)
        packet['listener_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            recorder.append(40, 0, packet)
        for stream in recorder.streams.values():
            stream.close()

    def test_rejects_frame_gap_and_missing_native_light_readback(self):
        recorder = self.recorder()
        recorder.append(40, 0, self.packet(40))
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            recorder.append(42, .05, self.packet(42))
        self.ego.get_light_state = None
        with self.assertRaisesRegex(ValueError, 'readback unavailable'):
            recorder.append(41, .05, self.packet(41))
        for stream in recorder.streams.values():
            stream.close()

    def test_no_pedestrian_affected_records_explicit_audio_absence(self):
        recorder = self.recorder()
        for i in range(3):
            self.ego.x = i
            self.ego.yaw = 20 if i == 2 else 0
            self.ego.lights = 1 if i >= 1 else 0
            recorder.append(40 + i, i / 20, None)
        recorder.close()
        result = measure(self.root / 'ego_turn_motion.jsonl', self.root / 'ego_signal_audio.jsonl',
                         self.root / 'affected_participants.json', self.root / 'participant_bodies.jsonl')
        self.assertIsNone(result['max_pre_turn_listener_audio_rms'])
        self.assertEqual(result['pre_turn_indicator_frames'], [41])


if __name__ == '__main__':
    unittest.main()
