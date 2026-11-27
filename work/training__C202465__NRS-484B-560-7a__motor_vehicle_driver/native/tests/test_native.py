"""Offline checks for the exact railroad crossing construction."""
import json
from pathlib import Path
import unittest

from runner import check
from source_review import load


class RailConstructionTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_case(self):
        result = check(self.config)
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['native_executed'])

    def test_identity_cannot_drift(self):
        altered = dict(self.config, actor='cycle_or_scooter_operator')
        with self.assertRaisesRegex(ValueError, 'identity'):
            check(altered)

    def test_original_review_required(self):
        with self.assertRaisesRegex(ValueError, 'Original reviewed rail source missing'):
            load(Path('missing-original-review'), '0' * 64)


if __name__ == '__main__':
    unittest.main()
