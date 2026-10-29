import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('analyze_case',ROOT/'analyze.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class TestExactCase(unittest.TestCase):
 def test_selected_measurements_and_geometry(self):
  import runner
  runner.check()
  contract=json.loads((ROOT/'config.json').read_text())['measurement_contract']
  for row in contract['requirements']:
   self.assertTrue(callable(getattr(mod,row['method'])))
   self.assertTrue(row['inputs'])
  self.assertEqual(contract['negative']['error_contains'],'Missing required source: '+contract['negative']['remove'][0])
if __name__=='__main__':unittest.main()
