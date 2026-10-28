import json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from worker_exchange.common import read,write,sha
from worker_exchange.execution_manifest import validate
from worker_exchange.runtime_cli import materialize,offline

class HandoffTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);self.aid='testing__C1__L1__driver';self.folder=self.root/'work'/self.aid;self.folder.mkdir(parents=True)
  runtime=self.root/'runtime';runtime.mkdir();(runtime/'source.py').write_text('pass\n');write(runtime/'SOURCE-MANIFEST.json',{'files':{'source.py':sha(runtime/'source.py')}})
  # Manifest preflight needs the actual ontology even in this miniature runtime.
  import shutil
  ontology=pathlib.Path(__file__).resolve().parents[1]/'library/TrafficSpec/Core/Vocab/Ontology/Ids.lean'
  target=runtime/'library/TrafficSpec/Core/Vocab/Ontology/Ids.lean';target.parent.mkdir(parents=True);shutil.copyfile(ontology,target)
  decoder=ontology.parents[2]/'Runtime/Decode.lean'
  target=runtime/'library/TrafficSpec/Core/Runtime/Decode.lean';target.parent.mkdir(parents=True);shutil.copyfile(decoder,target)
  write(self.root/'batch.json',{'runtime':{'root':'runtime'}})
  self.case=self.aid+'__probe';desc={'channels':[],'context_inputs':[],'limitations':[]}
  write(self.folder/'proposals/cases.json',{'cases':[{'case_id':self.case,'target_type':'boundary_probe','recording_description':desc}],'sweep_specs':[],'sweeps_expanded':True})
  script='import argparse\np=argparse.ArgumentParser();p.add_argument("--check",action="store_true");a=p.parse_args();assert a.check\n'
  self.bundle={'case_id':self.case,'entrypoint':'runner.py','recording_description':desc,'files':[{'path':'runner.py','content':script},{'path':'config.json','content':json.dumps({'selected_case_id':self.case})},{'path':'tests/test_fixture.py','content':'import unittest\nclass T(unittest.TestCase):\n def test_fixture(self):self.assertTrue(True)\n'}]}
  write(self.folder/'construction.json',self.bundle)
  self.manifest={'format':'worker-execution-manifest-v1','assignment_id':self.aid,'runtime_manifest_sha256':sha(runtime/'SOURCE-MANIFEST.json'),'cases':[{'case_id':self.case,'kind':'delivery','construction':'construction.json','construction_sha256':sha(self.folder/'construction.json')}]}
  write(self.folder/'execution-manifest.json',self.manifest)
 def test_valid_manifest(self):self.assertEqual(validate(self.root,self.aid)['cases'][0]['case_id'],self.case)
 def test_materialize_and_offline_without_simulator(self):
  self.assertTrue(offline(self.folder/'execution-manifest.json',self.case,self.root/'attempt',sys.executable)['offline_passed'])
 def test_no_undefined_or_duplicate_case(self):
  self.manifest['cases'].append(self.manifest['cases'][0]);write(self.folder/'execution-manifest.json',self.manifest)
  with self.assertRaises(ValueError):validate(self.root,self.aid)
 def test_reject_dynamic_unexpanded_sweep(self):
  p=read(self.folder/'proposals/cases.json');p['sweep_specs']=[{}];p['sweeps_expanded']=False;write(self.folder/'proposals/cases.json',p)
  with self.assertRaisesRegex(ValueError,'Expand'):validate(self.root,self.aid)
 def test_reject_missing_materialized_construction(self):
  self.manifest['cases'][0]['construction_sha256']='0'*64;write(self.folder/'execution-manifest.json',self.manifest)
  with self.assertRaises(ValueError):validate(self.root,self.aid)
 def test_no_overwriting_attempt(self):
  materialize(self.folder/'execution-manifest.json',self.case,self.root/'attempt')
  with self.assertRaises(ValueError):materialize(self.folder/'execution-manifest.json',self.case,self.root/'attempt')
 def test_capability_needs_analysis(self):
  self.manifest['cases'][0]['kind']='capability';write(self.folder/'execution-manifest.json',self.manifest)
  with self.assertRaises(ValueError):validate(self.root,self.aid)

 def test_local_manifest_bridge_uses_exact_stage(self):
  from unittest.mock import patch
  from worker_exchange.local import adopt_manifest_case
  with patch('worker_exchange.exchange.check_return'),patch('worker_exchange.local.adopt',return_value={'simulation_dispatched':False}) as adopter:
   result=adopt_manifest_case(self.root,self.root,'batch','unused.sqlite','run',self.aid,self.case,71,'exact-cache')
   self.assertFalse(result['simulation_dispatched']);self.assertEqual(result['recording_role'],'delivery_candidate')
   plan=read(adopter.call_args[0][-1]);self.assertEqual(plan['job_id'],71);self.assertEqual(plan['proposal'],'construction.json')
