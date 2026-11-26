"""Run the independent source and comparison negative proofs as CPU tests."""

import sys
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))

from prove_comparisons import main as prove_comparisons
from prove_original_branches import main as prove_original_branches


class CpuProofs(unittest.TestCase):
    def test_original_source_readback_and_missing_source_rejections(self):
        prove_original_branches()

    def test_selected_comparison_isolation_and_original_source_rejections(self):
        prove_comparisons()


if __name__ == "__main__":
    unittest.main()
