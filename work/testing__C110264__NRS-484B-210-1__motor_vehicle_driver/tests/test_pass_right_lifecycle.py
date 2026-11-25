"""CPU lifecycle ordering checks for later local Native orchestration."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_lifecycle import ORDER, validate_order


class LifecycleTests(unittest.TestCase):
    def test_owner_release_precedes_saved_processing(self):
        self.assertTrue(validate_order(list(ORDER))['saved_processing_after_release'])
        bad = list(ORDER)
        bad[-1], bad[-2] = bad[-2], bad[-1]
        with self.assertRaisesRegex(ValueError, 'before Native ownership release'):
            validate_order(bad)

    def test_missing_restoration_refused(self):
        with self.assertRaisesRegex(ValueError, 'before Native ownership release'):
            validate_order([event for event in ORDER if event != 'restoration_verified'])


if __name__ == '__main__':
    unittest.main()
