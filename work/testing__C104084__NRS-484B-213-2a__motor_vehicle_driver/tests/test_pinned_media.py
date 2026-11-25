"""Exercise the pinned saved-processing source-video contract directly."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.media import check_four_view_sources
from worker_exchange.saved_processing import prepare_video


class PinnedMediaTests(unittest.TestCase):
    def test_role_named_full_resolution_sources_and_wrong_size(self):
        scratch = REPO / '.runtime-work' / 'c104084-pinned-media-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            sources = {}
            for name, size in (('overview', '1920x1080'),
                               ('approach', '1280x720'),
                               ('reference_corner', '1280x720'),
                               ('driver_reference', '1280x720')):
                path = root / f'{name}.mkv'
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                                '-i', f'color=c=blue:s={size}:r=20', '-frames:v',
                                '2', '-c:v', 'libx264rgb', '-qp', '0', '-pix_fmt',
                                'rgb24', str(path)], check=True)
                sources[name] = path
            check_four_view_sources(sources)
            (root / 'video_frames.jsonl').write_text(''.join(
                json.dumps({'video_frame': frame, 'carla_frame': frame,
                            'time_s': frame / 20}) + '\n' for frame in range(2)))
            prepare_video(root)
            self.assertTrue((root / 'raw.mkv').is_file())
            self.assertTrue((root / 'four-view-receipt.json').is_file())
            bad = root / 'bad.mkv'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                            '-i', 'color=c=blue:s=64x48:r=20', '-frames:v', '2',
                            '-c:v', 'libx264rgb', '-qp', '0', '-pix_fmt', 'rgb24',
                            str(bad)], check=True)
            sources['approach'] = bad
            with self.assertRaisesRegex(ValueError, 'dimensions or rate differ'):
                check_four_view_sources(sources)


if __name__ == '__main__':
    unittest.main()
