import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.capture import PROFILE, layout
from worker_exchange.media import frames


class PortableContractTests(unittest.TestCase):
    def test_layout_has_unscaled_detail_views(self):
        value = layout(PROFILE['overview'], PROFILE['detail_views'])
        self.assertEqual((value['width'], value['height']), (3840, 1800))
        self.assertEqual(value['views']['overview'], [960, 0, 1920, 1080])

    def test_p6_pixels_include_whitespace_bytes(self):
        pixel = b'\n\x00\xff'
        values = list(frames(io.BytesIO(b'P6\n1 1\n255\n' + pixel)))
        self.assertEqual(values[0].pixels, pixel)

    def test_truncation_is_not_a_complete_frame(self):
        with self.assertRaises(ValueError):
            list(frames(io.BytesIO(b'P6\n1 1\n255\n\x00')))
