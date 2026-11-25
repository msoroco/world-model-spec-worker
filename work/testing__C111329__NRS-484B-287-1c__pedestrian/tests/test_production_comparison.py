import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from production_comparison import audit_pair


class ProductionComparisonTests(unittest.TestCase):
    def test_requires_distinct_original_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "distinct original attempts"):
                audit_pair("between_intersections_marking", directory, directory, {}, {})

    def test_invokes_production_source_audit_for_both_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left"
            right = Path(directory) / "right"
            left.mkdir()
            right.mkdir()
            with patch("production_comparison.audit_original", side_effect=ValueError(
                    "Native original source missing")) as audit:
                with self.assertRaisesRegex(ValueError, "Native original source missing"):
                    audit_pair("both_devices_operating", left, right, {}, {})
            self.assertEqual(audit.call_args.args[2], {})
            self.assertEqual(audit.call_count, 1)


if __name__ == "__main__":
    unittest.main()
