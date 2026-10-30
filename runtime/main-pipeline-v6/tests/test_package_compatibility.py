import unittest,tempfile,json,sys,hashlib,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from worker_exchange.common import read,write,sha,tree,digest
from worker_exchange.package_compatibility import check_receipts,CHECKS
class ProofTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.folder=self.root/'work/assignment';self.folder.mkdir(parents=True);self.fixture=self.root/'work/_shared/fixture';self.fixture.mkdir(parents=True);(self.fixture/'trace.jsonl').write_text('source')
  config={'required_atoms':['kin.speed']};self.files=[{'path':'config.json','content':json.dumps(config)},{'path':'analyze.py','content':'pass'},{'path':'runner.py','content':'capture()'}]
  write(self.folder/'construction.json',{'files':self.files,'recording_description':{'channels':[{'name':'kin.speed'}]}})
  self.entry={'case_id':'case','construction':'construction.json','construction_sha256':sha(self.folder/'construction.json'),'measurement_procedure':{'entrypoint':'analyze.py'},'acquisition':{'kin.speed':{'entrypoint':'runner.py','method':'native velocity','evidence':['trace.jsonl']}},'compatibility':{'receipt':'proof.json','fixture':'work/_shared/fixture','log':'analysis.log'}}
  (self.folder/'analysis.log').write_text('');self.proof={'log_sha256':sha(self.folder/'analysis.log'),'format':'worker-package-compatibility-v1','case_id':'case','passed':True,'checks':list(CHECKS),'construction_sha256':self.entry['construction_sha256'],'runtime_manifest_sha256':'runtime','fixture_sha256':digest(tree(self.fixture)),'analysis_sha256':hashlib.sha256(b'pass').hexdigest()};self.save();self.manifest={'runtime_manifest_sha256':'runtime','cases':[self.entry]}
 def save(self):write(self.folder/'proof.json',self.proof);self.entry['compatibility']['sha256']=sha(self.folder/'proof.json')
 def test_valid(self):self.assertTrue(check_receipts(self.root,self.folder,self.manifest))
 def test_old_ready_rejected(self):
  self.entry.pop('compatibility')
  with self.assertRaisesRegex(ValueError,'Missing package'):check_receipts(self.root,self.folder,self.manifest)
 def test_stale_construction(self):
  self.proof['construction_sha256']='old';self.save()
  with self.assertRaisesRegex(ValueError,'Stale'):check_receipts(self.root,self.folder,self.manifest)
 def test_stale_fixture(self):
  (self.fixture/'trace.jsonl').write_text('changed')
  with self.assertRaisesRegex(ValueError,'fixture changed'):check_receipts(self.root,self.folder,self.manifest)
 def test_missing_acquisition(self):
  self.entry['acquisition']={}
  with self.assertRaisesRegex(ValueError,'acquisition'):check_receipts(self.root,self.folder,self.manifest)
 def test_missing_downstream_stage(self):
  self.proof['checks'].remove('native_validation');self.save()
  with self.assertRaisesRegex(ValueError,'Incomplete'):check_receipts(self.root,self.folder,self.manifest)
 def test_stale_analysis(self):
  self.proof['analysis_sha256']='old';self.save()
  with self.assertRaisesRegex(ValueError,'analysis changed'):check_receipts(self.root,self.folder,self.manifest)
