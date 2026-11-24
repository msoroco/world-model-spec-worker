import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_media_audit import _frames_from_framemd5


class FullDecodeShapeTests(unittest.TestCase):
    def test_contiguous_decoded_frames(self):
        lines = '#format: frame checks\n0, 0, 0, 1, 1, abc\n0, 1, 1, 1, 1, def\n'
        self.assertEqual(_frames_from_framemd5(lines), [0, 1])

    def test_missing_or_discontinuous_frames_rejected(self):
        for lines in ('# empty\n', '0, 0, 0, 1, 1, abc\n0, 2, 2, 1, 1, def\n',
                      '0, 0, 0, 1, 1, \n'):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                _frames_from_framemd5(lines)


if __name__ == '__main__':
    unittest.main()
