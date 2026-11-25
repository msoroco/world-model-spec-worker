import json
import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_case_capture_profile(self):
        config = check(Path(__file__).resolve().parents[1])
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(config['frame_count'], 900)
        self.assertEqual(len(config['cameras']), 4)

if __name__ == '__main__':
    unittest.main()
