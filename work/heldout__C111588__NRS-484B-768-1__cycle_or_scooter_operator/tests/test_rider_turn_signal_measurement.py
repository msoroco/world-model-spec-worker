from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rider_turn_signal_measurement import measure


class RiderSignalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'driver_reference.mkv').write_bytes(b'CPU synthetic RGB source marker')
        digest = sha256((self.root / 'driver_reference.mkv').read_bytes()).hexdigest()
        self.motion = [{'frame': 10 + i, 'time_s': i * .05,
                        'rider_yaw_deg': yaw} for i, yaw in enumerate((0, 0, 25, 80))]
        self.reviews = [{'frame': 10 + i, 'time_s': i * .05, 'rider_id': 'rider-1',
                         'source_video_sha256': digest,
                         'visible_signal': i == 1,
                         'signal_type': 'left_arm' if i == 1 else 'none'}
                        for i in range(4)]
        self.context = {'rider_id': 'rider-1', 'device_type': 'electric_scooter',
                        'device_type_source': 'original blueprint and rider identification',
                        'on_roadway': True, 'roadway_source': 'original map and camera',
                        'designated_turn_lane': {'value': False, 'source_ref': 'original lane sign review'},
                        'both_hands_required_for_safety': {'value': None, 'source_ref': None}}

    def write(self):
        (self.root / 'rider_motion.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in self.motion))
        (self.root / 'rider_signal_review.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in self.reviews))
        (self.root / 'rider_context.json').write_text(json.dumps(self.context))

    def result(self):
        return measure(self.root / 'rider_motion.jsonl',
                       self.root / 'rider_signal_review.jsonl',
                       self.root / 'rider_context.json',
                       self.root / 'driver_reference.mkv')

    def test_single_visible_frame_before_turn_is_reported(self):
        self.write()
        result = self.result()
        self.assertEqual(result['turn_onset_frame'], 12)
        self.assertEqual(result['pre_turn_visible_signal_frames'], [11])
        self.assertTrue(result['pre_turn_signal_observation_complete'])
        self.assertIsNone(result['appropriate_signal_legal_judgment'])

    def test_no_signal_and_unknown_frame_remain_distinct(self):
        self.reviews[1]['visible_signal'] = False
        self.reviews[1]['signal_type'] = 'none'
        self.write()
        self.assertEqual(self.result()['pre_turn_visible_signal_frames'], [])
        self.reviews[1]['visible_signal'] = None
        self.reviews[1]['signal_type'] = 'unknown'
        self.write()
        self.assertFalse(self.result()['pre_turn_signal_observation_complete'])

    def test_rejects_stale_video_or_frame_join(self):
        self.write()
        (self.root / 'driver_reference.mkv').write_bytes(b'different source')
        with self.assertRaisesRegex(ValueError, 'no longer binds retained video'):
            self.result()
        digest = sha256((self.root / 'driver_reference.mkv').read_bytes()).hexdigest()
        for row in self.reviews:
            row['source_video_sha256'] = digest
        self.reviews[1]['frame'] = 99
        self.write()
        with self.assertRaisesRegex(ValueError, 'frame or rider join'):
            self.result()

    def test_rejects_uncited_exception_or_invalid_signal(self):
        self.context['both_hands_required_for_safety'] = {'value': True, 'source_ref': None}
        self.write()
        with self.assertRaisesRegex(ValueError, 'needs source'):
            self.result()
        self.context['both_hands_required_for_safety']['source_ref'] = 'original rider/control review'
        self.reviews[1]['signal_type'] = 'none'
        self.write()
        with self.assertRaisesRegex(ValueError, 'needs observed arm'):
            self.result()


if __name__ == '__main__':
    unittest.main()
