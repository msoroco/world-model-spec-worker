"""Original delivery media must meet the selected four-view profile."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import importlib.util
import json
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'c104538_delivery_audit', ROOT / 'native/delivery_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class DeliveryMediaTest(unittest.TestCase):
    def test_pixel_review_requires_each_visible_source(self):
        marks = [{'sign_visible': True, 'rider_visible': True,
                  'machine_visible': True}]
        audit.check_pixel_presence(marks)
        for field in ('sign_visible', 'rider_visible', 'machine_visible'):
            changed = [dict(marks[0])]
            changed[0][field] = False
            with self.assertRaisesRegex(ValueError, 'lacks visible ' + field):
                audit.check_pixel_presence(changed)

    def test_full_frame_size_and_rate(self):
        scratch = ROOT.parents[1] / '.runtime-work'
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            camera = Path(temporary) / 'approach.mkv'
            camera.write_bytes(b'unit-test-media')
            stream = {'nb_read_frames': '600', 'width': 1280,
                      'height': 720, 'r_frame_rate': '20/1'}

            def probe(*_args, **_kwargs):
                return SimpleNamespace(returncode=0,
                                       stdout=json.dumps({'streams': [stream]}))

            with mock.patch.object(audit.subprocess, 'run', side_effect=probe):
                receipt = audit.decode(camera, expected_size=(1280, 720))
                self.assertEqual((receipt['frames'], receipt['width'],
                                  receipt['height'], receipt['fps']),
                                 (600, 1280, 720, 20))
                for field, wrong in (('nb_read_frames', '599'),
                                     ('width', 640),
                                     ('r_frame_rate', '19/1')):
                    original = stream[field]
                    stream[field] = wrong
                    with self.assertRaisesRegex(ValueError, 'frame, size or rate'):
                        audit.decode(camera, expected_size=(1280, 720))
                    stream[field] = original
