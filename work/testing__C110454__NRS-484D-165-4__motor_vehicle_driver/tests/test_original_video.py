"""Original camera archives must encode to source-joined lossless movies."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera_recorder import VIEWS, encode_original_videos


class OriginalVideoTests(unittest.TestCase):
    def test_four_movies_decode_and_reject_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [{'video_frame': i, 'carla_frame': i + 25, 'time_s': i / 20}
                    for i in range(3)]
            for view in VIEWS:
                with zipfile.ZipFile(root / (view + '.zip'), 'w') as archive:
                    for row in rows:
                        image = Image.new('RGB', (16, 8), (row['video_frame'] * 70, 20, 4))
                        data = io.BytesIO()
                        image.save(data, format='PNG')
                        archive.writestr(str(row['carla_frame']) + '.png', data.getvalue())
            videos = encode_original_videos(root, rows)
            self.assertEqual(set(videos), set(VIEWS))
            for view in VIEWS:
                movie = root / videos[view]['path']
                probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                        '-select_streams', 'v:0', '-show_entries',
                                        'stream=nb_read_frames', '-of', 'json', str(movie)],
                                       capture_output=True, text=True, check=True)
                self.assertEqual(int(json.loads(probe.stdout)['streams'][0]['nb_read_frames']), 3)
            with self.assertRaisesRegex(ValueError, 'frame map invalid'):
                encode_original_videos(root, [{'video_frame': 9, 'carla_frame': 25}])


if __name__ == '__main__':
    unittest.main()
