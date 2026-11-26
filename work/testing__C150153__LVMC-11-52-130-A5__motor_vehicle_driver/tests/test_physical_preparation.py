"""Synthetic joins exercise preparation without claiming original Native review."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from parking import CASES
from physical_preparation import prepare
from test_independent_delivery_audit import sha
from test_physical_review import PhysicalReviewTests


class PhysicalPreparationTests(unittest.TestCase):
    def test_exact_case_matrix_and_provenance_rejection(self):
        scratch = Path('.runtime-work/c150153-physical-preparation-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        for case in CASES:
            with self.subTest(case=case.id), TemporaryDirectory(dir=scratch) as temp:
                attempt, site, sources, claim, packet, delivery = PhysicalReviewTests().fixture(temp, case.id)
                sealed = json.loads((attempt / 'capture-seal.json').read_text())
                with patch('physical_preparation.review', return_value=delivery):
                    result = prepare(attempt, site, sources, claim, sha(claim),
                                     diagnostic_fixture=True)
                    self.assertEqual(result['physical_checks']['maneuver']['status'], 'met')
                    self.assertEqual(result['provenance_kind'], 'synthetic_fixture')
                    self.assertFalse(result['original_pixel_review_joined'])
                    self.assertIsNone(result['legal_judgment'])
                    with self.assertRaisesRegex(ValueError, 'original Native provenance'):
                        prepare(attempt, site, sources, claim, sha(claim))
                    wrong = dict(delivery, case_id=delivery['case_id'] + '-changed')
                    with patch('physical_preparation.review', return_value=wrong):
                        with self.assertRaisesRegex(ValueError, 'review binding differs'):
                            prepare(attempt, site, sources, claim, sha(claim),
                                    diagnostic_fixture=True)
                (attempt / 'history.jsonl').write_text('changed original history\n')
                with self.assertRaisesRegex(ValueError, 'sealed history differs'):
                    prepare(attempt, site, sources, claim, sha(claim),
                            diagnostic_fixture=True)
                self.assertEqual(sealed['sources']['history.jsonl'] != sha(attempt / 'history.jsonl'), True)


if __name__ == '__main__':
    unittest.main()
