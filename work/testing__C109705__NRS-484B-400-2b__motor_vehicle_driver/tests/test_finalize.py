import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_saved_delivery import CASE, fixture

spec = importlib.util.spec_from_file_location('departure_finalize', Path(__file__).resolve().parents[1] / 'finalize.py')
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


class FinalizerTests(unittest.TestCase):
    def test_saved_only_measurement_and_no_legal_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            output = root / 'report.json'
            finalizer.finalize(root, path, case_id=CASE, output_path=output,
                               allow_diagnostic=True)
            result = json.loads(output.read_text())
            self.assertEqual(result['original_frame_count'], 900)
            self.assertEqual(result['source_manifest_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(len(result['observation']['per_frame']), 500)
            self.assertIsNone(result['observation']['statutory_judgment'])
            self.assertFalse(result['checks']['actual_pixels'])
            with self.assertRaises(FileExistsError):
                finalizer.finalize(root, path, case_id=CASE, output_path=output,
                                   allow_diagnostic=True)

    def test_rejected_delivery_or_stale_source_never_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = fixture(root)
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            output = root / 'report.json'
            with self.assertRaisesRegex(ValueError, 'original Native acquisition'):
                finalizer.finalize(root, path, case_id=CASE, output_path=output)
            self.assertFalse(output.exists())
            (root / 'original' / 'dash.media').write_text('tampered\n')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                finalizer.finalize(root, path, case_id=CASE, output_path=output,
                                   allow_diagnostic=True)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
