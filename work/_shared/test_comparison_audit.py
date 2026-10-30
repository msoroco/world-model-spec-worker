import json,tempfile,unittest
from pathlib import Path
from comparison_audit import audit
class ComparisonTests(unittest.TestCase):
 def fixture(self,root):
  index={}
  for cid,value in [('near',1),('far',2)]:
   report=root/(cid+'-report.json');config=root/(cid+'-config.json')
   report.write_text(json.dumps({'case_id':cid,'measurements':{'offset':{'value':value}}}))
   config.write_text(json.dumps({'selected_case_id':cid,'duration_s':45,'route':'same'}))
   index[cid]={'analysis_report':str(report),'config':str(config)}
  spec={'comparison_id':'position','case_ids':['near','far'],'fixed_config_selectors':['duration_s','route'],'checks':[{'name':'offset direction','case_ids':['near','far'],'selector':'measurements.offset.value','operator':'strictly_increasing'}]}
  return spec,index
 def test_saved_comparison(self):
  with tempfile.TemporaryDirectory() as t:
   spec,index=self.fixture(Path(t));result=audit(spec,index)
   self.assertTrue(result['passed']);self.assertFalse(result['native_replay_requested']);self.assertEqual(set(result['source_hashes']),{'near','far'})
 def test_reject_lost_isolation(self):
  with tempfile.TemporaryDirectory() as t:
   spec,index=self.fixture(Path(t));path=Path(index['far']['config']);d=json.loads(path.read_text());d['route']='different';path.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'changed fixed configuration'):audit(spec,index)
 def test_reject_failed_contrast(self):
  with tempfile.TemporaryDirectory() as t:
   spec,index=self.fixture(Path(t));path=Path(index['far']['analysis_report']);d=json.loads(path.read_text());d['measurements']['offset']['value']=0;path.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'Measured comparison failed'):audit(spec,index)
 def test_reject_identity_swap(self):
  with tempfile.TemporaryDirectory() as t:
   spec,index=self.fixture(Path(t));index['far']=index['near']
   with self.assertRaisesRegex(ValueError,'identity differs'):audit(spec,index)
 def test_reject_changed_acquisition(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);spec,index=self.fixture(root);source=root/'source.json';source.write_text('{}')
   report=Path(index['near']['analysis_report']);d=json.loads(report.read_text());d['measurements']['offset']['sources']={'source.json':'0'*64};report.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'acquisition source changed'):audit(spec,index)
if __name__=='__main__':unittest.main()
