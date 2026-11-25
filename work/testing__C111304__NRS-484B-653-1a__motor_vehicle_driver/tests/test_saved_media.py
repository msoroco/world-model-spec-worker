import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import saved_media
from test_carla_adapter import cameras


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture(root):
    picture = Image.new('RGB', (2, 2), (20, 40, 60))
    stream = io.BytesIO()
    picture.save(stream, format='PNG')
    png = stream.getvalue()
    channels = ('front', 'rear', 'left', 'right')
    for name in channels:
        (root / 'cameras' / name).mkdir(parents=True)
    rows = []
    for frame in range(100, 1000):
        rows.append({'original_frame': frame,
                     'camera_sha256': {name: sha(png) for name in channels}})
        for name in channels:
            (root / 'cameras' / name / f'{frame:06d}.png').write_bytes(png)
    encoded_rows = b''.join(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n'
                            for row in rows)
    (root / 'original-cameras.jsonl').write_bytes(encoded_rows)
    plan = cameras()
    canonical_plan = json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()
    receipt = {'case_id': 'testing__C111304__NRS-484B-653-1a__motor_vehicle_driver__person_north_early',
               'frame_count': 900, 'original_fps': 20, 'first_original_frame': 100,
               'camera_plan_sha256': sha(canonical_plan),
               'original_cameras_sha256': sha(encoded_rows)}
    (root / 'native-receipt.json').write_text(json.dumps(receipt) + '\n', encoding='utf-8')
    return plan


class SavedMediaTests(unittest.TestCase):
    def test_900_frame_source_join_and_full_decode(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = fixture(root)
            inventory = saved_media.encode_original_cameras(root, plan)
            self.assertEqual(set(inventory['cameras']), {'front', 'rear', 'left', 'right'})
            self.assertTrue((root / 'camera-media-inventory.json').is_file())
            self.assertEqual(inventory['source_kind'], 'original_encoded')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                saved_media.encode_original_cameras(root, plan)

    def test_changed_original_png_rejected_before_conversion(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = fixture(root)
            (root / 'cameras' / 'front' / '000100.png').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'original PNG hash mismatch'):
                saved_media.encode_original_cameras(root, plan)
            self.assertFalse((root / 'encoded').exists())

    def test_redirected_camera_directory_rejected(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as other:
            root = Path(tmp)
            plan = fixture(root)
            original = root / 'cameras' / 'front'
            moved = Path(other) / 'front'
            original.rename(moved)
            original.symlink_to(moved, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'missing or redirected'):
                saved_media.encode_original_cameras(root, plan)
            self.assertFalse((root / 'encoded').exists())


if __name__ == '__main__':
    unittest.main()
