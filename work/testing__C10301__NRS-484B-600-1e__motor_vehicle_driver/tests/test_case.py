import unittest
from pathlib import Path
from analyze import speed_history,highway_context
class CaseTest(unittest.TestCase):
 def test_missing_source(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: alley_context.json"):highway_context(Path("/nonexistent"))
 def test_speed_samples(self):
  self.assertTrue(callable(speed_history))
