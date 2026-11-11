import json
from pathlib import Path
import sys
import tempfile
import unittest


folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
from turn_signal_measurement import measure


class TurnSignalMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.motion = [{'frame': 40 + i, 'time_s': i / 20,
                        'ego_yaw_deg': yaw} for i, yaw in enumerate((0, 0, 20))]
        self.signals = [{'frame': 40 + i, 'time_s': i / 20,
                         'listener_id': 'pedestrian_1',
                         'indicator_readback': 'left' if i else 'off',
                         'listener_audio_samples': [amplitude] * 8}
                        for i, amplitude in enumerate((0, .2, 0))]
        self.context = {'pedestrian_may_be_affected': True,
                        'pedestrian_may_be_affected_source': 'reviewed approach corridor',
                        'vehicle_may_be_affected': True,
                        'vehicle_may_be_affected_source': 'reviewed conflict trajectory',
                        'listener_id': 'pedestrian_1',
                        'listener_position_source': 'original actor transform'}

    def write(self):
        (self.root / 'ego_turn_motion.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in self.motion))
        (self.root / 'ego_signal_audio.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in self.signals))
        (self.root / 'affected_participants.json').write_text(json.dumps(self.context))

    def result(self):
        return measure(self.root / 'ego_turn_motion.jsonl',
                       self.root / 'ego_signal_audio.jsonl',
                       self.root / 'affected_participants.json')

    def test_measures_pre_turn_audio_and_indicator_without_legal_label(self):
        self.write()
        result = self.result()
        self.assertEqual(result['turn_onset_frame'], 42)
        self.assertEqual(result['turn_direction'], 'left')
        self.assertEqual(result['pre_turn_indicator_frames'], [41])
        self.assertAlmostEqual(result['max_pre_turn_listener_audio_rms'], .2)
        self.assertIsNone(result['clearly_audible_legal_judgment'])

    def test_rejects_command_only_audio_and_wrong_listener(self):
        self.signals[1]['listener_audio_samples'] = []
        self.write()
        with self.assertRaisesRegex(ValueError, 'at least eight samples'):
            self.result()
        self.signals[1]['listener_audio_samples'] = [.2] * 8
        self.signals[1]['listener_id'] = 'other'
        self.write()
        with self.assertRaisesRegex(ValueError, 'Listener identity differs'):
            self.result()

    def test_rejects_missing_potential_effect_source_and_frame_join(self):
        self.context['pedestrian_may_be_affected_source'] = ''
        self.write()
        with self.assertRaisesRegex(ValueError, 'separately cited context'):
            self.result()
        self.context['pedestrian_may_be_affected_source'] = 'reviewed approach corridor'
        self.signals[1]['time_s'] = .2
        self.write()
        with self.assertRaisesRegex(ValueError, 'signal/audio frame join'):
            self.result()

    def test_rejects_nonfinite_original_audio_yaw_and_time(self):
        self.signals[1]['listener_audio_samples'] = [float('nan')] * 8
        self.write()
        with self.assertRaisesRegex(ValueError, 'out of range'):
            self.result()
        self.signals[1]['listener_audio_samples'] = [.2] * 8
        self.motion[2]['ego_yaw_deg'] = float('inf')
        self.write()
        with self.assertRaisesRegex(ValueError, 'yaw is not finite'):
            self.result()
        self.motion[2]['ego_yaw_deg'] = 20
        self.motion[1]['time_s'] = float('nan')
        self.signals[1]['time_s'] = float('nan')
        self.write()
        with self.assertRaisesRegex(ValueError, 'frame/time identity missing'):
            self.result()


if __name__ == '__main__':
    unittest.main()
