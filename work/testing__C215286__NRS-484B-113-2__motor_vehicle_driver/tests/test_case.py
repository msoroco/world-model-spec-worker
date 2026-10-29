import tempfile,unittest
from pathlib import Path
from analyze import reverse_crosswalk_overlap
class CrosswalkTest(unittest.TestCase):
 def test_missing_reverse_history(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'crosswalk_context.json').write_text('{"band_xy_m":[-8.45,-7.05,-7,7]}')
   with self.assertRaisesRegex(ValueError,'Missing required source: reverse_history.jsonl'):reverse_crosswalk_overlap(Path(d))
