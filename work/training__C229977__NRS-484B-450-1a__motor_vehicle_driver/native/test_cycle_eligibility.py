"""Exact source and actor negative-eligibility checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cycle_eligibility import ASSIGNMENT, check

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / 'inputs' / ASSIGNMENT / 'assignment.json'
CASE = ASSIGNMENT + '__probe_2'


class CycleEligibilityTests(unittest.TestCase):
    def test_exact_actor_excludes_all_three_classes(self):
        result = check(SOURCE, hashlib.sha256(SOURCE.read_bytes()).hexdigest(), [CASE])
        self.assertEqual(result['eligible_subsection_3_classes'], [])
        self.assertEqual(len(result['source_named_classes']), 3)
        self.assertFalse(result['cycle_branch_runnable_here'])

    def test_changed_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            check(SOURCE, '0' * 64, [CASE])

    def test_changed_actor_rejected(self):
        source = json.loads(SOURCE.read_text())
        source['actor'] = 'bicycle_rider'
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as tmp:
            path = Path(tmp) / 'assignment.json'
            path.write_text(json.dumps(source) + '\n')
            with self.assertRaisesRegex(ValueError, 'actor binding'):
                check(path, hashlib.sha256(path.read_bytes()).hexdigest(), [CASE])

    def test_unqualified_case_rejected(self):
        with self.assertRaisesRegex(ValueError, 'exact motor-vehicle'):
            check(SOURCE, hashlib.sha256(SOURCE.read_bytes()).hexdigest(), ['other__case'])


if __name__ == '__main__':
    unittest.main()
