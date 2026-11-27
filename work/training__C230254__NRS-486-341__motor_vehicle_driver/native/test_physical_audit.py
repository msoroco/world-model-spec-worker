import tempfile
import unittest
from pathlib import Path

from physical_audit import assess
from test_comparison_audit import make_case


class PhysicalTest(unittest.TestCase):
    def test_original_motion_and_stationary_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / "moving"
            make_case(attempt, "full_lane_available", "full_lane_available", 4)
            self.assertEqual(assess(attempt)["status"], "met")
            rows = (attempt / "lane-use-source.jsonl").read_text().splitlines()
            (attempt / "lane-use-source.jsonl").write_text(rows[0] + "\n" + rows[0] + "\n")
            with self.assertRaisesRegex(ValueError, "source join differs"):
                assess(attempt)

    def test_missing_context_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / "moving"
            make_case(attempt, "full_lane_available", "full_lane_available", 4)
            (attempt / "lane-use-context.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                assess(attempt)


if __name__ == "__main__":
    unittest.main()
