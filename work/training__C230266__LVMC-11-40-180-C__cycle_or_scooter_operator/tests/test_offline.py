import json
import unittest
from pathlib import Path
from runner import RiderPolicy, check
from audio_source import validate_source
import hashlib
import tempfile

HERE = Path(__file__).resolve().parent.parent


class SidewalkOffline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HERE/'config.json').read_text())

    def test_full_duration_and_sidewalk(self):
        summary = check(self.config)
        self.assertEqual(summary['frames'], 600)
        self.assertEqual(summary['sidewalk_lane_id'], -2)
        self.assertEqual(len(summary['cameras']), 4)
        self.assertFalse(summary['native_imported'])

    def test_signal_request_timing(self):
        policy = RiderPolicy(self.config)
        requested = [i for i in range(600) if policy.request(i)['audible_signal_request']]
        self.assertEqual(requested, [] if self.config['signal_frame'] is None else [self.config['signal_frame']])
        self.assertEqual(policy.request(90)['forward_speed_mps'],
                         0 if self.config['pause_window_frames'] == [80, 110] else 1.4)
        self.assertEqual(policy.request(120)['forward_speed_mps'], 1.4)

    def test_missing_microphone_rejected(self):
        modified = dict(self.config)
        modified['pedestrian_microphone'] = {'location': 'rider_actor'}
        with self.assertRaisesRegex(ValueError, 'pedestrian location'):
            check(modified)

    def test_wrong_camera_rejected(self):
        modified = dict(self.config)
        modified['cameras'] = self.config['cameras'][:3]
        with self.assertRaisesRegex(ValueError, 'Four original'):
            check(modified)

    def test_original_microphone_integrity_and_frame_join(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            pcm = output/'pedestrian-microphone.s16le'
            pcm.write_bytes(b'\x00\x00\x40\x00')
            metadata = {'source_kind':'live_external_microphone',
                        'pcm_path':pcm.name,'sample_rate_hz':8000,'channels':1,
                        'pcm_sha256':hashlib.sha256(pcm.read_bytes()).hexdigest(),
                        'pcm_bytes':4,'start_monotonic_ns':1,
                        'first_chunk_monotonic_ns':2,
                        'device_placement_verified':False}
            (output/'pedestrian-microphone.json').write_text(json.dumps(metadata)+'\n')
            (output/'pedestrian-microphone-frames.jsonl').write_text(
                json.dumps({'video_frame':0,'native_frame':100,'monotonic_ns':3})+'\n'+
                json.dumps({'video_frame':1,'native_frame':101,'monotonic_ns':4})+'\n')
            self.assertEqual(validate_source(output,expected_frames=2)['frames'],2)
            pcm.write_bytes(b'\x00\x00\x41\x00')
            with self.assertRaisesRegex(ValueError,'bytes changed'):
                validate_source(output,expected_frames=2)


if __name__ == '__main__':
    unittest.main()
