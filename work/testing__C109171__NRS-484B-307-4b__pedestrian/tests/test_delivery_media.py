import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_media import PROFILE_SIZES, audit_delivery_media
from native_scene import SourceError


class DeliveryMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'camera_png').mkdir()
        events = []
        mapping = []
        for frame in range(2):
            events.append({'frame': frame, 'sim_time_seconds': frame * 0.05})
            row = {'frame': frame, 'sim_time_seconds': frame * 0.05, 'cameras': {}}
            for name, size in PROFILE_SIZES.items():
                stream = io.BytesIO()
                Image.new('RGB', size, (frame + 1, 2, 3)).save(stream, format='PNG')
                raw = stream.getvalue()
                path = self.root / 'camera_png' / f'{frame:04d}_{name}.png'
                path.write_bytes(raw)
                row['cameras'][name] = {
                    'path': path.relative_to(self.root).as_posix(),
                    'sha256': hashlib.sha256(raw).hexdigest()}
            mapping.append(row)
        self.events_ref = self.write('events.json', events)
        self.map_ref = self.write('map.json', mapping)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_exact_profile_pixels_and_source_join(self):
        receipt = audit_delivery_media(self.root, self.map_ref, self.events_ref, 2)
        self.assertEqual(receipt['decoded_source_frames'], 8)
        self.assertTrue(receipt['pinned_dimensions_verified'])
        self.assertEqual(receipt['statutory_permission'], 'unresolved')

    def test_rehashed_wrong_dimensions_still_rejected(self):
        path = self.root / 'camera_png/0001_approach.png'
        stream = io.BytesIO()
        Image.new('RGB', (4, 4), (1, 2, 3)).save(stream, format='PNG')
        path.write_bytes(stream.getvalue())
        mapping = json.loads((self.root / self.map_ref['path']).read_text())
        mapping[1]['cameras']['approach']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.map_ref = self.write('map.json', mapping)
        with self.assertRaisesRegex(SourceError, 'dimensions differ'):
            audit_delivery_media(self.root, self.map_ref, self.events_ref, 2)

    def test_changed_original_pixel_rejected_even_if_same_dimensions(self):
        path = self.root / 'camera_png/0000_overview.png'
        stream = io.BytesIO()
        Image.new('RGB', PROFILE_SIZES['overview'], (9, 8, 7)).save(stream, format='PNG')
        path.write_bytes(stream.getvalue())
        with self.assertRaisesRegex(SourceError, 'camera source hash mismatch'):
            audit_delivery_media(self.root, self.map_ref, self.events_ref, 2)


if __name__ == '__main__':
    unittest.main()
