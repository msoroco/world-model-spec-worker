import json,unittest
from pathlib import Path
from runner import check,read_original
class TestRunner(unittest.TestCase):
 def test_exact(self):
  c=json.loads(Path('config.json').read_text());self.assertEqual(check(c)['frames'],600)
 def test_source_required(self):
  with self.assertRaisesRegex(ValueError,'Original alley context and hour ledger required'):read_original(None,None)
if __name__ == '__main__':unittest.main()
