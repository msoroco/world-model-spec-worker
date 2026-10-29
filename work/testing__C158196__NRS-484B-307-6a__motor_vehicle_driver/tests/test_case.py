import unittest
from pathlib import Path
from analyze import entry_order
class SignalCase(unittest.TestCase):
 def test_missing_original_sequence(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: signal_history.jsonl"):entry_order(Path("/nonexistent"))
