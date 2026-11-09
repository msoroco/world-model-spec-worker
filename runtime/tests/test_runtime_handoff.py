import json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from worker_exchange.common import read,write,sha,tree
from worker_exchange.execution_manifest import validate
from worker_exchange.runtime_cli import materialize,offline

class HandoffTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);self.aid='testing__C1__L1__driver';self.folder=self.root/'work'/self.aid;self.folder.mkdir(parents=True)
  runtime=self.root/'runtime';runtime.mkdir();(runtime/'source.py').write_text('pass\n');write(runtime/'SOURCE-MANIFEST.json',{'files':{'source.py':sha(runtime/'source.py')}})
  write(self.root/'batch.json',{'runtime':{'root':'runtime'}})
  self.case=self.aid+'__probe';desc={'channels':[],'context_inputs':[],'limitations':[]}
  write(self.folder/'proposals/cases.json',{'cases':[{'case_id':self.case,'target_type':'boundary_probe','recording_description':desc}],'sweep_specs':[],'sweeps_expanded':True})
  script='import argparse\np=argparse.ArgumentParser();p.add_argument("--check",action="store_true");a=p.parse_args();assert a.check\n'
  self.bundle={'case_id':self.case,'entrypoint':'runner.py','recording_description':desc,'files':[{'path':'runner.py','content':script},{'path':'config.json','content':json.dumps({'selected_case_id':self.case})},{'path':'tests/test_fixture.py','content':'import unittest\nclass T(unittest.TestCase):\n def test_fixture(self):self.assertTrue(True)\n'}]}
  write(self.folder/'construction.json',self.bundle)
  self.manifest={'format':'worker-execution-manifest','assignment_id':self.aid,'runtime_manifest_sha256':sha(runtime/'SOURCE-MANIFEST.json'),'cases':[{'case_id':self.case,'kind':'delivery','construction':'construction.json','construction_sha256':sha(self.folder/'construction.json')}]}
  # Exercise the real current manifest validators, using software-only diagnostic
  # outcomes and the unchanged observation Core. No simulator is contacted.
  import shutil
  from traffic_spec_adapter.adapter import full_core
  local_library=pathlib.Path(__file__).resolve().parents[1]/'library'
  if not local_library.is_dir():
   local_library=pathlib.Path(__file__).resolve().parents[2]/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/library'
  shutil.copytree(full_core(local_library),runtime/'library/TrafficSpec/Core')
  write(runtime/'SOURCE-MANIFEST.json',{'files':{k:v for k,v in tree(runtime).items() if k!='SOURCE-MANIFEST.json'}})
  self.manifest['runtime_manifest_sha256']=sha(runtime/'SOURCE-MANIFEST.json')
  self.bundle.update(cell_id='C1',actor='driver')
  self.bundle['files'].append({'path':'analyze.py','content':'def measure(): return 1\n'})
  write(self.folder/'construction.json',self.bundle)
  entry=self.manifest['cases'][0];entry['construction_sha256']=sha(self.folder/'construction.json')
  (self.folder/'offline.log').write_text('offline check passed')
  entry.update(offline={'exit_code':0,'construction_sha256':entry['construction_sha256'],'command':'runner --check','log':'offline.log','log_sha256':sha(self.folder/'offline.log')},candidate_risk={'status':'none','reason':'Static software fixture has no Native motion'},candidates=[],measurement_procedure={'entrypoint':'analyze.py'},measurement_contract='measurement.json',fixture_recipe='work/'+self.aid+'/recipe.json',native_handoff={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'})
  row={'status':'selected_required','requirement':'position','source':'law'}
  write(self.folder/'case-plan.json',{'law_id':'L1','cell_id':'C1','requirement_dispositions':[row]})
  write(self.folder/'measurement.json',{'format':'worker-measurement-contract','requirements':[dict(disposition_index=0,requirement='position',source='law',output_key='position',method='measure',value_type='number',kind='measured',inputs=['position.json'])],'negative':{'remove':['position.json'],'error_contains':'Missing required source: position.json'}})
  write(self.folder/'position.json',{'position':1})
  write(self.folder/'recipe.json',{'format':'worker-fixture-recipe','sources':[{'path':'position.json','source':'work/'+self.aid+'/position.json','sha256':sha(self.folder/'position.json')}]})
  fixtures=[]
  for kind,status in [('complete_motion','met'),('incomplete_motion','not_met'),('missing_evidence','unverified')]:
   log=kind+'.log';result=kind+'.json';(self.folder/log).write_text('synthetic outcome assertion passed')
   write(self.folder/result,{'physical_checks':{'maneuver':{'status':status,'method':'synthetic motion fixture','sources':['position.json']}},'maneuver_completed':status=='met','realized_observables':{'position':1},'provenance_kind':'native'})
   fixtures.append({'kind':kind,'exit_code':0,'command':'synthetic-outcome-test','log':log,'log_sha256':sha(self.folder/log),'result':result,'result_sha256':sha(self.folder/result)})
  lifecycle={'events':['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started'],'exit_code':0,'log':'offline.log','log_sha256':sha(self.folder/'offline.log')}
  write(self.folder/'physical-proof.json',{'construction_sha256':entry['construction_sha256'],'fixtures':fixtures,'lifecycle':lifecycle})
  entry['physical_preparation']={'receipt':'physical-proof.json','sha256':sha(self.folder/'physical-proof.json')}
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

 def test_exact_offline_proof_is_required_without_historical_flags(self):
  self.manifest['cases'][0].pop('offline');write(self.folder/'execution-manifest.json',self.manifest)
  with self.assertRaisesRegex(ValueError,'offline check missing'):validate(self.root,self.aid)
 def test_measurement_contract_is_required_without_historical_flags(self):
  (self.folder/'measurement.json').unlink()
  with self.assertRaisesRegex(ValueError,'measurement contract'):validate(self.root,self.aid)
 def test_lifecycle_source_tampering_is_rejected(self):
  (self.folder/'physical-proof.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'physical preparation'):validate(self.root,self.aid)
