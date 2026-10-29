import tempfile,unittest
from pathlib import Path
from analyze import interaction_timing,nearest_visible_point
class EntranceTest(unittest.TestCase):
 def test_missing_interaction_source(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: interaction_history.jsonl'):interaction_timing(Path(d))
 def test_missing_view_samples(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: view_samples.jsonl'):nearest_visible_point(Path(d))
