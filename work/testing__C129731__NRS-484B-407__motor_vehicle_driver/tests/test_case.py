import tempfile,unittest
from pathlib import Path
from analyze import visibility_500ft
class CurveTest(unittest.TestCase):
 def test_missing_original_sight(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: visibility_samples.jsonl'):visibility_500ft(Path(d))
