"""Use one synthetic four-view frame to check original-byte media encoding."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_camera import CameraRig, VIEWS
from native_media import finalize
from tests.test_native_camera import CameraWorld, packet_with_cameras
from tests.test_native_frame import Actor

REPO = Path(__file__).resolve().parents[3]


class NativeMediaTests(unittest.TestCase):
    def test_four_lossless_sources_and_changed_pixel_rejection(self):
        (REPO / '.runtime-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as temp:
            root = Path(temp)
            site = packet_with_cameras(root)
            world = CameraWorld()
            rig = CameraRig(world, Actor(1), site, 'stopped_leftmost_clear', root / 'raw',
                            lambda xyz, rpy: (xyz, rpy))
            world.emit(1)
            cameras = rig.await_frame(1, .05)
            rig.close()
            trace = root / 'trace.jsonl'
            trace.write_text(json.dumps({
                'case_id': rig.scene['case_id'], 'source_packet_sha256': rig.scene['source_packet_sha256'],
                'original_sample_claim': True, 'time_s': .05,
                'native_frame': {'origin': 'native_world_snapshot', 'frame': 1, 'time_s': .05,
                                 'original_cameras': cameras}}) + '\n')
            receipt = finalize(trace, root / 'raw', root)
            self.assertEqual(receipt['frames'], 1)
            self.assertEqual(set(receipt['video_sha256']), {name for name, _, _ in VIEWS})
            mapping = json.loads((root / 'video_frames.jsonl').read_text())
            self.assertEqual((mapping['video_frame'], mapping['carla_frame']), (0, 1))
            for name, width, height in VIEWS:
                probe = json.loads(subprocess.check_output([
                    'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
                    '-of', 'json', str(root / (name + '.mkv'))], text=True))['streams'][0]
                self.assertEqual((probe['width'], probe['height'], probe['codec_name']),
                                 (width, height, 'ffv1'))
                self.assertEqual(probe['r_frame_rate'], '20/1')
                decoded = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                                          '-i', str(root / (name + '.mkv')), '-f', 'null', '-'],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(decoded.returncode, 0, decoded.stderr.decode())
            with self.assertRaisesRegex(ValueError, 'retain previous camera media'):
                finalize(trace, root / 'raw', root)
            path = root / 'raw' / cameras['approach']['raw_bgra']
            with path.open('r+b') as stream:
                stream.write(b'BAD')
            with self.assertRaisesRegex(ValueError, 'pixel hash differs'):
                finalize(trace, root / 'raw', root / 'media-again')


if __name__ == '__main__':
    unittest.main()
