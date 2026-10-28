import json,pathlib,unittest,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[1]
class Example(unittest.TestCase):
 def test_offline(self):subprocess.run([sys.executable,str(R/'runner.py'),'--check'],check=True,capture_output=True)
 def test_capture_contract(self):
  d=json.loads((R/'original-construction.json').read_text());self.assertTrue(d['recording_description']['channels']);self.assertTrue(d['measurement_plan']);self.assertIn('runner.py',[f['path'] for f in d['files']])
 def test_case_identity(self):
  a=json.loads((R/'requirements.json').read_text());r=json.loads((R/'representative-result.json').read_text());self.assertEqual(a['actor'],r['actor']);self.assertEqual(a['cell']['cell_id'],r['cell_id'])
