import unittest
from pathlib import Path
from analyze import speed_history,posted_sign_context
class CaseTest(unittest.TestCase):
 def test_missing_source(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: posted_speed_context.json"):posted_sign_context(Path("/nonexistent"))
 def test_speed_samples(self):
  self.assertTrue(callable(speed_history))
