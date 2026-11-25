"""Offline exact identity and original-source gate checks."""
import json
from pathlib import Path
import unittest

from runner import check, _review_before_mutation


class RailConstructionTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_case(self):
        result = check(self.config)
        self.assertEqual(result["frames"], 600)
        self.assertFalse(result["native_executed"])

    def test_lane_count_cannot_drift(self):
        changed = dict(self.config)
        changed["marked_lane_count"] = 3
        with self.assertRaisesRegex(ValueError, "identity"):
            check(changed)

    def test_required_stop_source_missing(self):
        with self.assertRaisesRegex(ValueError, "Original reviewed rail source missing: required-stop"):
            _review_before_mutation(Path("missing-original-review"), "0" * 64, None, self.config)


if __name__ == "__main__":
    unittest.main()
