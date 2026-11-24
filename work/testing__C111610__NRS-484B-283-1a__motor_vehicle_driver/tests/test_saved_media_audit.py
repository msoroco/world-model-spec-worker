import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from native_capture import capture
from saved_media_audit import audit
from test_native_capture import Adapter, SCENE, packet


class SavedMediaAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work' / 'c111610-media-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.site = self.root / 'site.json'
        self.site.write_text(json.dumps(packet()) + '\n')
        self.exception = self.root / 'exception.json'
        self.exception.write_text(json.dumps({
            'case_id': json.loads(SCENE.read_text())['case_id'],
            'status': 'none_identified', 'source_refs': ['review/exception-source.json']}) + '\n')
        self.dims = {name: (2, 2) for name in
                     ('overview', 'approach', 'reference_corner', 'driver_reference')}
        self.attempt = self.root / 'attempt'
        capture(Adapter(self.site.read_bytes()), SCENE, self.site, self.exception,
                self.attempt, dimensions=self.dims)

    def test_full_decode_is_software_only(self):
        report = audit(self.attempt, SCENE, dimensions=self.dims)
        self.assertEqual(report['decoded_view_frames'], 2400)
        self.assertFalse(report['physical_acceptance'])
        self.assertEqual(report['pixel_visibility'], 'unreviewed')

    def test_changed_original_png_rejected(self):
        image = self.attempt / 'original-frames/overview-000011.png'
        image.write_bytes(image.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'camera bytes changed'):
            audit(self.attempt, SCENE, dimensions=self.dims)

    def test_frame_map_shift_rejected(self):
        path = self.attempt / 'frame_map.json'
        rows = json.loads(path.read_text())
        rows[10]['native_frame'] += 1
        path.write_text(json.dumps(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'source file hash'):
            audit(self.attempt, SCENE, dimensions=self.dims)


if __name__ == '__main__':
    unittest.main()
