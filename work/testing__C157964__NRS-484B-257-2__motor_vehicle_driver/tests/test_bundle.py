import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_officer_construction(self):
        config = check(Path(__file__).resolve().parents[1])
        self.assertEqual(config["frame_count"], 900)
        self.assertEqual(len(config["cameras"]), 4)

if __name__ == "__main__":
    unittest.main()
