import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_crest import audit_original_pngs, source_inventory, REQUIRED_SOURCES


class OriginalPngTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT.parents[1] / '.runtime-work' / 'c104084-png-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = ROOT.name + '__left_crest_obstructed'
        self.hashes = {}
        frames = {}
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            rows = {}
            folder = self.root / 'original-png' / camera
            folder.mkdir(parents=True)
            for frame in (10, 11):
                path = folder / f'{frame:08d}.png'
                Image.new('RGB', (2, 2), (frame, 0, 0)).save(path)
                rows[str(frame)] = hashlib.sha256(path.read_bytes()).hexdigest()
            frames[camera] = rows
        manifest = {'format': 'c104084-original-camera-pngs-v1',
                    'case_id': self.case, 'frames': frames}
        path = self.root / 'original-png-manifest.json'
        path.write_text(json.dumps(manifest) + '\n')
        self.hashes['original-png-manifest.json'] = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_four_camera_original_pixels_join(self):
        audit_original_pngs(self.root, self.hashes, self.case, [10, 11])

    def test_changed_original_pixel_rejected(self):
        path = self.root / 'original-png' / 'approach' / '00000011.png'
        Image.new('RGB', (2, 2), (0, 0, 0)).save(path)
        with self.assertRaisesRegex(ValueError, 'original PNG source differs'):
            audit_original_pngs(self.root, self.hashes, self.case, [10, 11])

    def test_900_frame_production_inventory_requires_pixels(self):
        hashes = {name: 'a' * 64 for name in REQUIRED_SOURCES}
        with self.assertRaisesRegex(ValueError, 'wrong exact sources'):
            source_inventory(hashes, self.case, 900)


if __name__ == '__main__':
    unittest.main()
