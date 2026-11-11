import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_deferred_audio import DeferredTurnSourceRecorder
from turn_signal_measurement import measure


class Actor:
    def __init__(self, x, y, yaw=0, lights=0):
        self.x, self.y, self.yaw, self.lights = x, y, yaw, lights
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=1., y=.5))

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=self.y),
                               rotation=SimpleNamespace(yaw=self.yaw))

    def get_light_state(self):
        return self.lights


class DeferredAudioTest(unittest.TestCase):
    def make_recorder(self, root):
        ego = Actor(-5, 0, lights=1)
        listener = Actor(2, 2)
        context = {'pedestrian_may_be_affected': True,
                   'pedestrian_may_be_affected_source': 'original route and pedestrian transforms',
                   'vehicle_may_be_affected': False,
                   'vehicle_may_be_affected_source': 'original no-vehicle participant inventory',
                   'participant_types': {'ped_listener': 'pedestrian'},
                   'listener_position_source': 'original pedestrian transform',
                   'participant_geometry_source': 'original actor bounds'}
        recorder = DeferredTurnSourceRecorder(root, ego, {'ped_listener': listener},
                                              'ped_listener', context, 1, 2)
        for frame in range(3):
            ego.x += 1
            ego.yaw = 0 if frame == 0 else frame * 3
            recorder.append(40 + frame, frame * .05)
        recorder.close_raw()
        return recorder

    def test_joins_original_wav_after_native_frames(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = self.make_recorder(root)
            wav = root / 'listener.wav'
            with wave.open(str(wav), 'wb') as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(160)
                stream.writeframes(struct.pack('<' + 'h' * 24, *([1000] * 24)))
            manifest = recorder.finalize_audio(wav, source_start_time_s=0,
                                                capture_provenance='independent listener microphone')
            value = measure(*(root / name for name in (
                'ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
                'affected_participants.json', 'participant_bodies.jsonl')))
            self.assertEqual(value['frame_count'], 3)
            self.assertGreater(value['max_pre_turn_listener_audio_rms'], 0)
            self.assertEqual(value['pre_turn_indicator_frames'], [40])
            self.assertEqual(manifest['frames'], 3)
            packet = json.loads((root / 'listener_audio_original.jsonl').read_text().splitlines()[0])
            self.assertEqual(packet['capture_source_sha256'], manifest['listener_wav_sha256'])

    def test_rejects_missing_or_misaligned_listener_source(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = self.make_recorder(root)
            with self.assertRaisesRegex(ValueError, 'Original listener WAV'):
                recorder.finalize_audio(root / 'missing.wav', source_start_time_s=0,
                                        capture_provenance='independent listener microphone')


if __name__ == '__main__':
    unittest.main()
