import unittest
from pathlib import Path
from analyze import rows
class DarkSignalCase(unittest.TestCase):
 def test_missing_original_history(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: interaction_history.jsonl"):rows(Path("/nonexistent"))
