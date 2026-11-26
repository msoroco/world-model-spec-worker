"""Selected CPU proof invariants; fixtures do not attest original capture."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = ('reference', 'contrast', 'engine_on', 'brake_unset', 'wheel_straight')


class SelectedEvidenceTest(unittest.TestCase):
    def test_all_selected_cases_have_positive_and_missing_source_saved_paths(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        self.assertEqual({case['case_id'].rsplit('__', 1)[1] for case in manifest['cases']}, set(SUFFIXES))
        for suffix in SUFFIXES:
            folder = ROOT / 'proofs' / suffix
            positive = json.loads((folder / 'saved-positive.log').read_text())
            missing = json.loads((folder / 'saved-missing.log').read_text())
            self.assertTrue(positive['passed'] and positive['recorded_only'])
            self.assertFalse(positive['missing_evidence'])
            self.assertTrue(missing['passed'] and missing['recorded_only'])
            self.assertTrue(missing['missing_evidence'])
            self.assertTrue(positive['synthetic_cpu_fixture'])
            self.assertTrue(missing['synthetic_cpu_fixture'])

    def test_engine_actuator_receipt_is_required_by_independent_audit(self):
        for suffix in SUFFIXES:
            folder = ROOT / 'proofs' / suffix
            self.assertIn('Original engine actuator preparation missing',
                          (folder / 'delivery-negative.log').read_text())
            self.assertTrue((folder / 'delivery-positive.log').read_text().strip())

    def test_four_isolated_comparison_fixture_paths(self):
        summary = json.loads((ROOT / 'proofs/comparison-cpu.log').read_text())
        self.assertEqual(summary['passed'], 4)
        self.assertTrue(summary['synthetic_cpu_fixture'])
        self.assertEqual(len(set(summary['comparison_ids'])), 4)


if __name__ == '__main__':
    unittest.main()
