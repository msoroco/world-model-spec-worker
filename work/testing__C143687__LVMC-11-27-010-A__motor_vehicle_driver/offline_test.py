"""Offline exact trail bundle checks, with explicit diagnostic provenance."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from runner import check_bundle


class OfflineBundleTests(unittest.TestCase):
    def test_exact_source_bound_diagnostic_construction(self):
        result = check_bundle(Path(__file__).resolve().parents[1])
        self.assertEqual(result['source_count'], 9)
        self.assertEqual(result['construction_calls'], 4)
        self.assertTrue(result['diagnostic_fixture'])
        self.assertFalse(result['native_started'])
        self.assertIsNone(result['legal_judgment'])

    def test_reject_changed_original_source_bytes(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'bundle'
            shutil.copytree(root, copied)
            (copied / 'sources' / 'map.txt').write_text('changed map')
            with self.assertRaisesRegex(ValueError, 'map source hash mismatch'):
                check_bundle(copied)


if __name__ == '__main__':
    unittest.main()
