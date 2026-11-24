import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


FINALIZER = module('saved_finalizer_test', 'saved_finalizer.py')
CAPTURE = module('native_capture_for_finalizer_test', 'native_capture.py')
SPEC = importlib.util.spec_from_file_location('native_capture_fixture_for_finalizer', Path(__file__).with_name('test_native_capture.py'))
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


def original(root, case_id, merge=True):
    data = FIXTURE.readings(root, merge=merge)
    for old_camera in (root / 'camera').rglob('*.png'):
        old_camera.unlink()
    for row in data:
        row.pop('camera_sources')
        row['camera_images'] = {
            view: SimpleNamespace(frame=row['frame'], width=2, height=2,
                                  raw_data=bytes([12, 34, 56, 255] * 4))
            for view in CAPTURE.VIEWS}
    wrapped = CAPTURE.sensor_frame_reader(root, data.__getitem__,
                                          {view: (2, 2) for view in CAPTURE.VIEWS})
    CAPTURE.capture_original(root, case_id, FIXTURE.site(root), wrapped, len(data))
    return data


class SavedFinalizerTests(unittest.TestCase):
    def test_finalizes_original_merge_and_censored_cases(self):
        for case, merge in [('exact__below_50ft', True), ('exact__no_merge', False)]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                original(root, case, merge)
                result = FINALIZER.finalize_saved(root, case, 4, {view: (2, 2) for view in CAPTURE.VIEWS})
                self.assertEqual(result['case_id'], case)
                self.assertEqual(result['verified_frame_count'], 4)
                self.assertEqual(result['decoded_camera_images'], 16)
                self.assertEqual(result['merge_observed'], merge)
                self.assertIsNone(result['legal_judgment'])

    def test_rejects_identity_count_and_unrealized_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original(root, 'exact__below_50ft')
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                FINALIZER.finalize_saved(root, 'exact__above_50ft', 4, {view: (2, 2) for view in CAPTURE.VIEWS})
            with self.assertRaisesRegex(ValueError, 'incomplete original frame count'):
                FINALIZER.finalize_saved(root, 'exact__below_50ft', 5, {view: (2, 2) for view in CAPTURE.VIEWS})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original(root, 'exact__below_50ft', merge=False)
            with self.assertRaisesRegex(ValueError, 'no observed merge'):
                FINALIZER.finalize_saved(root, 'exact__below_50ft', 4, {view: (2, 2) for view in CAPTURE.VIEWS})

    def test_rejects_changed_site_source_even_when_receipt_rehashed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original(root, 'exact__below_50ft')
            receipt_path = root / 'native/capture-receipt.json'
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            receipt['site_source'] = receipt['original_trace']
            receipt_path.write_text(json.dumps(receipt) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'public-highway|Native map'):
                FINALIZER.finalize_saved(root, 'exact__below_50ft', 4, {view: (2, 2) for view in CAPTURE.VIEWS})

    def test_rejects_hash_current_non_png_camera_and_profile_drift(self):
        import hashlib
        for replacement, error in [(b'not a PNG', 'cannot identify image'), (None, 'PNG profile mismatch')]:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                original(root, 'exact__below_50ft')
                target = root / 'camera/overview/000100.png'
                if replacement is not None:
                    target.write_bytes(replacement)
                else:
                    from PIL import Image
                    Image.new('RGB', (3, 3)).save(target)
                path = root / 'native/frame_map.json'
                frame_map = json.loads(path.read_text(encoding='utf-8'))
                frame_map['frames'][0]['camera_sha256']['overview'] = hashlib.sha256(target.read_bytes()).hexdigest()
                path.write_text(json.dumps(frame_map) + '\n', encoding='utf-8')
                receipt_path = root / 'native/capture-receipt.json'
                receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
                receipt['frame_map_source']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                receipt_path.write_text(json.dumps(receipt) + '\n', encoding='utf-8')
                with self.assertRaisesRegex((ValueError, OSError), error):
                    FINALIZER.finalize_saved(root, 'exact__below_50ft', 4,
                                             {view: (2, 2) for view in CAPTURE.VIEWS})


if __name__ == '__main__':
    unittest.main()
