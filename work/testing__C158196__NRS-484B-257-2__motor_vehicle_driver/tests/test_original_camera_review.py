"""Source and frame binding for the shared camera review index."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from original_camera_review import CAMERAS, build


class OriginalCameraReviewTest(unittest.TestCase):
    def test_build_and_changed_source_or_frame_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ('video_frames.jsonl', *(name + '.mkv' for name in CAMERAS))
            for name in names:
                (root / name).write_bytes(('source:' + name).encode())
            hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in names}
            frames = [{'video_frame': index, 'carla_frame': 100 + index,
                       'time_s': 5.0 + index / 20,
                       'camera_frames': {name: 100 + index for name in CAMERAS}}
                      for index in range(2)]
            record = build(root, frames, hashes)
            self.assertEqual(record['frame_count'], 2)
            self.assertEqual(record['visual_judgment'], 'unreviewed')
            self.assertEqual(record['source_sha256'], hashes)
            (root / 'approach.mkv').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Changed original camera'):
                build(root, frames, hashes)
            hashes['approach.mkv'] = hashlib.sha256(b'changed').hexdigest()
            frames[1]['camera_frames']['approach'] = 99
            with self.assertRaisesRegex(ValueError, 'frame join differs'):
                build(root, frames, hashes)


if __name__ == '__main__':
    unittest.main()
