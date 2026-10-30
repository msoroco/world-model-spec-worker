import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from worker_exchange.media import compose_four_views


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class FourViewCompositionTests(unittest.TestCase):
    def test_exact_sources_compose_and_missing_source_rejected(self):
        sizes = {'overview': (1920, 1080), 'approach': (1280, 720),
                 'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            videos = {}
            for name, (width, height) in sizes.items():
                path = root / (name + '.mkv')
                subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                                '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20',
                                '-frames:v', '1', '-c:v', 'ffv1', str(path)], check=True)
                videos[name] = path
            mapping = root / 'video_frames.jsonl'
            mapping.write_text(json.dumps({'video_frame': 0, 'carla_frame': 7, 'time_s': .05}) + '\n')
            result = compose_four_views(videos, mapping, root / 'raw.mkv')
            self.assertEqual((result['frames'], result['dimensions']), (1, [3840, 1800]))
            self.assertFalse(result['pixel_visibility_verified'])
            with self.assertRaisesRegex(ValueError, 'prior composed source'):
                compose_four_views(videos, mapping, root / 'raw.mkv')
            videos['approach'].unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original camera source'):
                compose_four_views(videos, mapping, root / 'new.mkv')
