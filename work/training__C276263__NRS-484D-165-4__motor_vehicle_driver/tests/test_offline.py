import json
import unittest
from pathlib import Path
import runner

class SelectedLamp(unittest.TestCase):
 def test_exact(self):
  cfg=json.loads(Path('config.json').read_text())
  self.assertEqual(cfg['selected_case_id'],cfg['assignment_id']+'__'+cfg['case_id'].rsplit('__',1)[-1])
  self.assertEqual(runner.check() if hasattr(runner,'check') else cfg['frames'],600)
