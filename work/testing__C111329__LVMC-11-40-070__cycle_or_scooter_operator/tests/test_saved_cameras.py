import hashlib
import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import capture
from native_cameras import CAMERAS
from saved_camera_audit import audit
from test_native_capture import Bike, World, officer_reader
from test_saved_instruction import CASE, SITE, SITE_SHA


def png():
    stream = BytesIO()
    Image.new('RGB', (4, 4), (10, 20, 30)).save(stream, format='PNG')
    return stream.getvalue()


class TestSavedCameras(unittest.TestCase):
    def test_original_four_camera_capture_and_decode(self):
        scratch = REPO / '.runtime-work/c111329-tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            world = World()
            bike = Bike(world)
            device = type('Device', (), {'id': 10})()
            payload = png()
            readers = {name: (lambda frame, value=payload: {'frame': frame, 'png_bytes': value})
                       for name in CAMERAS}
            dimensions = {name: (4, 4) for name in CAMERAS}
            trace = root / 'instruction.json'
            result = capture(world, bike, device, CASE, SITE, SITE_SHA,
                             lambda _device, _snapshot: 'red', officer_reader,
                             trace, readers, dimensions)
            self.assertEqual(result['frame_count'], 900)
            value = audit(trace, hashlib.sha256(trace.read_bytes()).hexdigest(), CASE['case_id'])
            self.assertEqual(value['decoded_images'], 3600)
            self.assertFalse(value['physical_acceptance'])
            archive = root / 'overview.png.zip'
            original = archive.read_bytes()
            archive.write_bytes(original + b'tamper')
            with self.assertRaisesRegex(ValueError, 'camera source hash mismatch'):
                audit(trace, hashlib.sha256(trace.read_bytes()).hexdigest(), CASE['case_id'])
            archive.write_bytes(original)
            packet = json.loads(trace.read_text())
            packet['samples'][100]['time_s'] += 0.1
            trace.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'camera frame or time gap'):
                audit(trace, hashlib.sha256(trace.read_bytes()).hexdigest(), CASE['case_id'])

    def test_camera_frame_mismatch_removes_incomplete_archives(self):
        scratch = REPO / '.runtime-work/c111329-tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            world = World()
            bike = Bike(world)
            device = type('Device', (), {'id': 10})()
            payload = png()
            readers = {name: (lambda frame, value=payload: {'frame': frame, 'png_bytes': value})
                       for name in CAMERAS}
            readers['approach'] = lambda frame: {'frame': frame + 1, 'png_bytes': payload}
            with self.assertRaisesRegex(ValueError, 'camera frame identity mismatch'):
                capture(world, bike, device, CASE, SITE, SITE_SHA,
                        lambda _device, _snapshot: 'red', officer_reader,
                        root / 'instruction.json', readers,
                        {name: (4, 4) for name in CAMERAS})
            self.assertFalse((root / 'instruction.json').exists())
            self.assertFalse(any(root.glob('*.png.zip')))
            self.assertTrue(bike.braked)


if __name__ == '__main__':
    unittest.main()
