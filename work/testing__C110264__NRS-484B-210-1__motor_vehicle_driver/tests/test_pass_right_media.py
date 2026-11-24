"""Tiny diagnostic images exercise the archive decoder, never physical coverage."""
import io
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_media import audit_archive


def png(size=(8, 4)):
    out = io.BytesIO()
    Image.new('RGB', size, (37, 91, 126)).save(out, 'PNG')
    return out.getvalue()


def archive(path, names, size=(8, 4), broken_index=None):
    with ZipFile(path, 'w') as target:
        for index, name in enumerate(names):
            target.writestr(name, b'broken' if index == broken_index else png(size))


class TestOriginalCameraDecode(unittest.TestCase):
    def test_full_900_frame_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'original.zip'
            archive(path, [f'{index:06d}.png' for index in range(900)])
            result = audit_archive(path, (8, 4))
            self.assertEqual(result['frame_count'], 900)
            self.assertEqual(len(result['full_pixel_sha256']), 64)

    def test_rejects_missing_duplicate_and_reordered_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'original.zip'
            names = [f'{index:06d}.png' for index in range(900)]
            for bad in (names[:-1], names[:-1] + [names[-2]],
                        names[:400] + names[401:402] + names[400:401] + names[402:]):
                archive(path, bad)
                with self.assertRaisesRegex(ValueError, 'frame order/count'):
                    audit_archive(path, (8, 4))

    def test_rejects_wrong_size_and_corrupt_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'original.zip'
            names = [f'{index:06d}.png' for index in range(900)]
            archive(path, names, size=(9, 4))
            with self.assertRaisesRegex(ValueError, 'dimensions'):
                audit_archive(path, (8, 4))
            archive(path, names, broken_index=400)
            with self.assertRaisesRegex(ValueError, 'full decode'):
                audit_archive(path, (8, 4))


if __name__ == '__main__':
    unittest.main()
