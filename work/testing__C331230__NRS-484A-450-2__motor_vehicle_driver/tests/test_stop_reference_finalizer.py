import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
import test_stop_reference as reference_fixture
spec=importlib.util.spec_from_file_location('stop_reference_finalizer',ROOT/'stop_reference_finalizer.py')
finalizer=importlib.util.module_from_spec(spec);spec.loader.exec_module(finalizer)
class StopReferenceFinalizerTests(unittest.TestCase):
 def fixture(self,root,line):
  reference_fixture.StopReferenceTests().fixture(root,line=line)
  suffix='no_crosswalk_marked_stop_line' if line else 'no_crosswalk_no_line_first_view'
  case=ROOT.name+'__'+suffix
  (root/'config.json').write_text(json.dumps({'assignment_id':ROOT.name,'selected_case_id':case,'law_id':'NRS-484A-450-2',
   'recording_description':{'channels':[],'context_inputs':[]},'physical_completion':{'criterion':'intersection_clearance',
   'motion_source':'stop_history.jsonl','body_key':'ego_body_vertices_xy_m',
   'intersection_polygon_xy_m':[[20,-5],[30,-5],[30,5],[20,5]],'exit_axis':0,'exit_sign':1,'minimum_progress_m':0.25}}))
  (root/'trace.jsonl').write_text(''.join(json.dumps({'frame':100+i,'time_s':1+i*.05,'position':{'x':x,'y':0},'speed_mps':0 if i==1 else 2})+'\n' for i,x in enumerate((0,5,11,22))))
  (root/'capture').mkdir();(root/'capture/evidence.jsonl').write_text('{}\n')
  for name in finalizer.CAMERAS:(root/(name+'.mkv')).write_bytes(b'fixture-camera-source')
  return case
 def test_saved_line_and_sight_output(self):
  for line in (True,False):
   with self.subTest(line=line),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);case=self.fixture(root,line);value=finalizer.finalize(root,root/'analysis.json')
    self.assertTrue(value['ordered']);self.assertEqual(json.loads((root/'result.json').read_text())['case_id'],case)
    self.assertFalse(json.loads((root/'analysis.json').read_text())['physical_acceptance_claimed'])
 def test_missing_sight_source_rejected_before_channels(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root,False);(root/'sight_history.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source'):finalizer.finalize(root,root/'analysis.json')
   self.assertFalse((root/'channels').exists())
if __name__=='__main__':unittest.main()
