"""Exercise lossless publication from retained original Native PNG bytes."""

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_media import encode
from saved_delivery import CAMERAS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeMediaTests(unittest.TestCase):
    def source(self, root):
        attempt, output = root / 'original', root / 'published'
        attempt.mkdir()
        output.mkdir()
        rows = [{'frame': 100 + index, 'video_frame': index}
                for index in range(3)]
        frame_map = attempt / 'video_frames.jsonl'
        frame_map.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        acquisition = {'video_frames.jsonl': {'kind': 'original_native',
                       'sha256': sha(frame_map)}, 'media': {}}
        for name in CAMERAS:
            source = attempt / (name + '.zip')
            with zipfile.ZipFile(source, 'w') as archive:
                for index, row in enumerate(rows):
                    buffer = io.BytesIO()
                    Image.new('RGB', (2, 2), (index * 40, 20, 30)).save(
                        buffer, format='PNG')
                    archive.writestr(f'{index:04d}-{row["frame"]}.png',
                                     buffer.getvalue())
            acquisition['media'][name] = {'kind': 'original_native',
                                          'path': source.name, 'sha256': sha(source)}
        (attempt / 'acquisition.json').write_text(json.dumps(acquisition))
        return attempt, output

    def test_four_original_archives_encode_and_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt, output = self.source(Path(temp))
            receipt = encode(attempt, output, {name: (2, 2) for name in CAMERAS})
            self.assertEqual(receipt['frames'], 3)
            self.assertFalse(receipt['physical_visibility_verified'])
            for name in CAMERAS:
                target = output / (name + '.mkv')
                self.assertEqual(sha(target), receipt['encoded_camera_sha256'][name])
                probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams',
                    'v:0', '-count_frames',
                    '-show_entries', 'stream=codec_name,width,height,nb_read_frames',
                    '-of', 'json', str(target)], capture_output=True, text=True,
                    check=True)
                stream = json.loads(probe.stdout)['streams'][0]
                self.assertEqual((stream['codec_name'], stream['width'],
                                  stream['height'], stream['nb_read_frames']),
                                 ('ffv1', 2, 2, '3'))

    def test_changed_original_archive_rejected_without_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt, output = self.source(Path(temp))
            with (attempt / 'overview.zip').open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'camera source differs'):
                encode(attempt, output, {name: (2, 2) for name in CAMERAS})
            self.assertFalse(any(output.iterdir()))

    def test_changed_original_frame_map_rejected_without_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt, output = self.source(Path(temp))
            with (attempt / 'video_frames.jsonl').open('a') as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'frame map source differs'):
                encode(attempt, output, {name: (2, 2) for name in CAMERAS})
            self.assertFalse(any(output.iterdir()))


if __name__ == '__main__':
    unittest.main()
