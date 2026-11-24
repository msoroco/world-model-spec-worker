import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_capture import capture
from saved_delivery import audit, audit_original_pixels
from test_approach import body, context
from test_native_map import CASE, FakeWorld


buffer = io.BytesIO()
Image.new('RGB', (2, 2), color=(12, 34, 56)).save(buffer, format='PNG')
PNG = buffer.getvalue()
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


class FakeAdapter:
    def __init__(self, *, drift_at=None, omit_camera=None, invalid_png=False):
        self.world = FakeWorld()
        self.count = 0
        self.drift_at = drift_at
        self.omit_camera = omit_camera
        self.invalid_png = invalid_png
        self.braked = False
        self.cleaned = False
        self.native_attested = False

    def start(self, plan):
        self.case_id = plan['case_id']

    def tick(self):
        index = self.count
        self.count += 1
        return {'frame': 100 + index,
                'time_s': index * .05 + (0.02 if index == self.drift_at else 0)}

    def read_ego(self, frame):
        index = frame - 100
        phase = 'approach' if index < 450 else 'departure'
        return {'frame': frame, 'case_id': self.case_id, 'phase': phase,
                'road_id': phase, 'ego_heading_rad': 0.0 if index < 450 else 1.2,
                'ego_body_vertices_xy_m': body(-.7)}

    def read_cameras(self, frame):
        raw = b'\x89PNG\r\n\x1a\n' + b'bad-image' if self.invalid_png else PNG
        return {name: {'frame': frame, 'png': raw}
                for name in CAMERAS if name != self.omit_camera}

    def brake(self):
        self.braked = True

    def cleanup(self):
        self.cleaned = True


def packet(path):
    source = '<OpenDRIVE>surveyed</OpenDRIVE>'
    value = {'context': context(), 'map_name': 'TownTest',
             'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
             'left_turn_route_waypoint_ids': [11, 12, 13],
             'ego_blueprint_id': 'vehicle.test',
             'camera_plan': 'four cameras, 20 Hz'}
    path.write_text(json.dumps(value))


class NativeCaptureTests(unittest.TestCase):
    def test_full_diagnostic_capture_and_saved_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            adapter = FakeAdapter()
            result = capture(adapter, CASE, survey, root / 'attempt')
            self.assertEqual(result['frame_count'], 900)
            self.assertTrue(adapter.braked and adapter.cleaned)
            with self.assertRaisesRegex(ValueError, 'diagnostic'):
                audit(root / 'attempt', CASE)
            reopened = audit(root / 'attempt', CASE, allow_diagnostic=True)
            self.assertTrue(reopened['source_integrity_passed'])
            self.assertFalse(reopened['physical_completion'])
            pixels = audit_original_pixels(root / 'attempt', CASE, allow_diagnostic=True)
            self.assertEqual(pixels['decoded_frames'], 3600)
            self.assertEqual(pixels['dimensions']['approach'], [2, 2])
            self.assertFalse(pixels['physical_completion'])

    def test_frame_drift_and_missing_camera_are_rejected_with_cleanup(self):
        for kwargs, error in (({'drift_at': 4}, 'cadence'),
                              ({'omit_camera': 'approach'}, 'four-camera')):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                survey = root / 'packet.json'
                packet(survey)
                adapter = FakeAdapter(**kwargs)
                with self.assertRaisesRegex(ValueError, error):
                    capture(adapter, CASE, survey, root / 'attempt')
                self.assertTrue(adapter.braked and adapter.cleaned)

    def test_invalid_image_bytes_fail_full_pixel_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            capture(FakeAdapter(invalid_png=True), CASE, survey, root / 'attempt')
            with self.assertRaisesRegex(ValueError, 'decode failed'):
                audit_original_pixels(root / 'attempt', CASE, allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
