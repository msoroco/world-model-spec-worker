import importlib.util,json,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('selected_analysis',ROOT/'analyze.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)
class ExactCase(unittest.TestCase):
 def test_selected_measurement_and_native_geometry(self):
  import runner
  runner.check()
  contract=json.loads((ROOT/'config.json').read_text())['measurement_contract']
  for row in contract['requirements']:
   self.assertTrue(callable(getattr(analysis,row['method'])))
   self.assertTrue(row['inputs'])
 def test_missing_case_source_rejected(self):
  with self.assertRaisesRegex(ValueError,'Missing required source: case_observations.jsonl'):
   analysis.source(ROOT/'missing-fixture-directory','case_observations.jsonl')
if __name__=='__main__':unittest.main()
