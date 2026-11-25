"""Exact comparison isolation using synthetic saved software fixtures."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from diagnostic_case_compatibility import run, ASSIGNMENT
from comparison_audit import audit


class ComparisonAuditTest(unittest.TestCase):
    def test_four_exact_pairs_and_original_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            attempts = {}
            for suffix in ('designated', 'opposed_reverse', 'lane2_designated',
                           'lane2_opposed_reverse'):
                root = base / suffix
                run(root, ASSIGNMENT + '__' + suffix)
                attempts[suffix] = root
            for comparison, a, b in (
                ('actual_direction_lane1', 'designated', 'opposed_reverse'),
                ('actual_direction_lane2', 'lane2_designated', 'lane2_opposed_reverse'),
                ('lane1_vs_lane2_designated', 'designated', 'lane2_designated'),
                ('lane1_vs_lane2_opposed', 'opposed_reverse', 'lane2_opposed_reverse')):
                with self.subTest(comparison=comparison):
                    left, right = attempts[a], attempts[b]
                    with self.assertRaisesRegex(ValueError, 'original comparison sources required'):
                        audit(left/'attempt', left/'positive', right/'attempt',
                              right/'positive', comparison)
                    receipt = audit(left/'attempt', left/'positive', right/'attempt',
                                    right/'positive', comparison, allow_diagnostic=True)
                    self.assertEqual(receipt['source_kind'], 'synthetic_software_fixture')
                    self.assertFalse(receipt['physical_acceptance_claimed'])
