import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finalize_delivery import finalize_saved
from intersection_observables import SourceError
from native_acquisition import acquire
from native_media import NativeMediaWriter
from test_native_acquisition import Actor, BOUNDARY, CASE, Controller, Observer, World
from test_native_media import Cameras


class SavedDeliveryTests(unittest.TestCase):
    def test_rejects_short_capture_even_with_all_four_camera_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                    'cpu-short', root, 3, NativeMediaWriter(root, Cameras()))
            with self.assertRaisesRegex(SourceError, 'complete 900-frame'):
                finalize_saved(root, expected_case=CASE)

    def test_rejects_missing_media_and_wrong_exact_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                    'cpu-unsealed-media', root, 3)
            with self.assertRaisesRegex(SourceError, 'saved exact case'):
                finalize_saved(root, expected_case=CASE.replace('inside_stop', 'inside_stand'))
            with self.assertRaisesRegex(SourceError, 'source manifest path differs: media'):
                finalize_saved(root, expected_case=CASE)


if __name__ == '__main__':
    unittest.main()
