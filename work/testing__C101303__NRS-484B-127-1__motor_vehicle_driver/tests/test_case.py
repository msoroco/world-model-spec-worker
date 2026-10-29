import unittest
from pathlib import Path
from analyze import following_gap
class CaseTest(unittest.TestCase):
 def test_missing_pair(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: following_samples.jsonl"):following_gap(Path("/nonexistent"))
