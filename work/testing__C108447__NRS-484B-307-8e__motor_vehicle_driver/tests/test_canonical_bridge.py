import json
import hashlib
import os
import struct
import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path
from unittest import mock
from zipfile import ZipFile

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from canonical_bridge import bridge
from saved_delivery import CAMERAS


def tiny_png(value):
    def chunk(name, payload):
        return (struct.pack('>I', len(payload)) + name + payload +
                struct.pack('>I', zlib.crc32(name + payload) & 0xffffffff))
    raw = b''.join(b'\x00' + bytes([value, 0, 0]) * 2 for _ in range(2))
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class CanonicalBridgeTests(unittest.TestCase):
    def test_two_original_frames_encode_and_seal(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temp:
            root = Path(temp)
            original = root / 'original-attempt'
            original.mkdir()
            ego = [{'frame': 100 + i, 'time_s': i / 20,
                    'x': float(i), 'y': 0.0, 'speed_mps': 1.0,
                    'yaw_rad': 0.0, 'velocity_mps': [1, 0, 0]}
                   for i in range(2)]
            (original / 'trace.json').write_text(json.dumps({'ego': ego}) + '\n')
            rows = []
            for i, body in enumerate(ego):
                cameras = {}
                for camera in CAMERAS:
                    data = tiny_png(32 + i * 100)
                    cameras[camera] = {'member': f'{body["frame"]}.png',
                                       'sha256': hashlib.sha256(data).hexdigest()}
                rows.append({'frame': body['frame'], 'time_s': body['time_s'],
                             'cameras': cameras})
            (original / 'frame-map.jsonl').write_text(''.join(
                json.dumps(row) + '\n' for row in rows))
            for camera in CAMERAS:
                with ZipFile(original / (camera + '.zip'), 'w') as archive:
                    for i, body in enumerate(ego):
                        archive.writestr(f'{body["frame"]}.png',
                                         tiny_png(32 + i * 100))
            for name in ('map-packet.json', 'authority.json', 'road.xodr'):
                (original / name).write_text('{}\n')
            native = root / 'capture'
            (native / 'native').mkdir(parents=True)
            (native / 'manifest.json').write_text(json.dumps({
                'frames': 2, 'observation_contract_version': 2}) + '\n')
            (native / 'native/frames.jsonl').write_text(
                '{"frame":100}\n{"frame":101}\n')
            (native / 'evidence.jsonl').write_text(''.join(
                json.dumps({'original_frame': body['frame'],
                            'replay_frame': body['frame'],
                            'recording_time_s': body['time_s']}) + '\n'
                for body in ego))
            release = {'world_restored': True, 'actors_released': True,
                       'sensors_released': True, 'readback_passed': True}
            package = types.ModuleType('worker_exchange')
            package.__path__ = []
            native_output = types.ModuleType('worker_exchange.native_output')
            native_output.seal_capture = mock.Mock(return_value={'sealed': True})
            with mock.patch.dict(sys.modules, {
                    'worker_exchange': package,
                    'worker_exchange.native_output': native_output}):
                result = bridge(root, original, release=release,
                                expected_frames=2)
            self.assertEqual(result['frame_count'], 2)
            self.assertEqual(result['capture_seal'], {'sealed': True})
            native_output.seal_capture.assert_called_once()
            self.assertEqual(len((root / 'trace.jsonl').read_text().splitlines()), 2)
            self.assertEqual(len((root / 'video_frames.jsonl').read_text().splitlines()), 2)
            for camera in CAMERAS:
                self.assertGreater((root / (camera + '.mkv')).stat().st_size, 0)

    def test_rejects_missing_owner_graph_before_seal(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temp:
            root = Path(temp)
            original = root / 'original-attempt'
            original.mkdir()
            (root / 'construction.json').write_text('{}\n')
            (root / 'runner.py').write_text('# original runner\n')
            ego = [{'frame': 100 + i, 'time_s': i / 20,
                    'x': float(i), 'y': 0.0, 'speed_mps': 1.0,
                    'yaw_rad': 0.0, 'velocity_mps': [1, 0, 0]}
                   for i in range(20)]
            (original / 'trace.json').write_text(json.dumps({'ego': ego}) + '\n')
            rows = [{'frame': item['frame'], 'time_s': item['time_s'],
                     'cameras': {}} for item in ego]
            (original / 'frame-map.jsonl').write_text(''.join(
                json.dumps(row) + '\n' for row in rows))
            for name in ('map-packet.json', 'authority.json', 'road.xodr'):
                (original / name).write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'owner must export original Native graph'):
                bridge(root, original, release={
                    'world_restored': True, 'actors_released': True,
                    'sensors_released': True, 'readback_passed': True},
                    expected_frames=20)
            self.assertFalse((root / 'capture-seal.json').exists())

    def test_rejects_owner_graph_frame_rebinding_before_video_encoding(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temp:
            root = Path(temp)
            original = root / 'original-attempt'
            original.mkdir()
            ego = [{'frame': 100 + i, 'time_s': i / 20,
                    'x': float(i), 'y': 0.0, 'speed_mps': 1.0,
                    'yaw_rad': 0.0, 'velocity_mps': [1, 0, 0]}
                   for i in range(2)]
            (original / 'trace.json').write_text(json.dumps({'ego': ego}) + '\n')
            (original / 'frame-map.jsonl').write_text(''.join(
                json.dumps({'frame': item['frame'], 'time_s': item['time_s'],
                            'cameras': {}}) + '\n' for item in ego))
            native = root / 'capture'
            (native / 'native').mkdir(parents=True)
            (native / 'manifest.json').write_text(json.dumps({
                'frames': 2, 'observation_contract_version': 2}) + '\n')
            (native / 'native/frames.jsonl').write_text(
                '{"frame":100}\n{"frame":999}\n')
            (native / 'evidence.jsonl').write_text(''.join(
                json.dumps({'original_frame': item['frame'],
                            'replay_frame': item['frame'],
                            'recording_time_s': item['time_s']}) + '\n'
                for item in ego))
            with self.assertRaisesRegex(ValueError, 'frame identity differs'):
                bridge(root, original, release={
                    'world_restored': True, 'actors_released': True,
                    'sensors_released': True, 'readback_passed': True},
                    expected_frames=2)
            self.assertFalse((root / 'trace.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
