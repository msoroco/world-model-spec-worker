"""Source-shaped saved-only directional proof; no original evidence claim."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SavedOnlyTest(unittest.TestCase):
    def test_four_variants_and_missing_scene(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from diagnostic_case_compatibility import run, ASSIGNMENT
        for suffix, direction in (('designated', 'designated'),
                                  ('opposed_reverse', 'opposed'),
                                  ('lane2_designated', 'designated'),
                                  ('lane2_opposed_reverse', 'opposed')):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                receipt = run(Path(tmp) / suffix, ASSIGNMENT + '__' + suffix)
                self.assertEqual(receipt['positive']['actual_direction'], direction)
                self.assertEqual(receipt['positive']['original_frame_count'], 900)
                self.assertEqual(receipt['positive']['source_kind'], 'synthetic_software_fixture')
                self.assertIn('Missing required source: diagnostic-scene.json',
                              receipt['negative_expected_error'])

    def test_original_path_rejects_diagnostic(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from diagnostic_case_compatibility import fixture, ASSIGNMENT
        from process_recorded_only import process
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case_id = ASSIGNMENT + '__designated'
            fixture(root / 'attempt', case_id)
            with self.assertRaisesRegex(ValueError, 'original reviewed site packet path required'):
                process(root / 'attempt', root / 'output', case_id)
