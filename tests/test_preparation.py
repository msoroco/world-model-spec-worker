import copy,json,pathlib,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'runtime/main-pipeline-v1/scenario_pipeline'))
from worker_exchange.common import read,write,sha,tree
from worker_exchange.preparation import check
from worker_exchange.updates import state,publish

class PreparationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=pathlib.Path(self.tmp.name)/'repo';self.r.mkdir();self.aid='testing__C1__L1__driver';self.d=self.r/'work'/self.aid
  write(self.r/'inputs'/self.aid/'assignment.json',{'actor':'driver','cell_id':'C1','law_id':'L1'})
  write(self.r/'partitions/01.json',{'assignment_ids':[self.aid]})
  self.batch={'mode':'six_step_preparation','batch_id':'batch','update_version':2,'assignments':{self.aid:{'input_sha256':sha(self.r/'inputs'/self.aid/'assignment.json')}},'frozen_files':tree(self.r)}
  write(self.r/'batch.json',self.batch)
  self.d.mkdir(parents=True);(self.d/'HANDOFF.md').write_text('Physical realization unverified')
  self.plan={'assignment_id':self.aid,'actor':'driver','cell_id':'C1','law_id':'L1','cases':[{'case_id':self.aid+'__a','target_law_id':'L1'}],'comparisons':[],'observations':[{'name':'pose'}],'sources':[{'path':'inputs/'+self.aid+'/assignment.json','sha256':sha(self.r/'inputs'/self.aid/'assignment.json')}],'existing_evidence':[],'runtime_uncertainties':['actual visibility']}
  write(self.d/'case-plan.json',self.plan)
  self.result={'assignment_id':self.aid,'input_sha256':self.batch['assignments'][self.aid]['input_sha256'],'status':'partial','applied_update':2,'reason':'capability unverified'}
  write(self.d/'result.json',self.result)
 def test_partial_is_validated(self):
  check(self.r,True)
  self.plan.pop('observations');write(self.d/'case-plan.json',self.plan)
  with self.assertRaisesRegex(ValueError,'observations'):check(self.r,True)
 def test_selected_branch_dispositions_required(self):
  original=read(self.r/'inputs'/self.aid/'assignment.json');original['branch']='selected witness';write(self.r/'inputs'/self.aid/'assignment.json',original)
  self.batch['assignments'][self.aid]['input_sha256']=sha(self.r/'inputs'/self.aid/'assignment.json')
  self.batch['frozen_files']={k:v for k,v in tree(self.r).items() if k!='batch.json' and not k.startswith('work/')}
  self.batch['selected_branch_dispositions_required']=True;write(self.r/'batch.json',self.batch)
  self.result['input_sha256']=self.batch['assignments'][self.aid]['input_sha256'];write(self.d/'result.json',self.result)
  self.plan['sources'][0]['sha256']=self.result['input_sha256'];write(self.d/'case-plan.json',self.plan)
  with self.assertRaisesRegex(ValueError,'Selected witness'):check(self.r,True)
  self.plan['selected_branch']='selected witness'
  self.plan['requirement_dispositions']=[{'requirement':'selected','source':'assignment.json','status':'selected_required','evidence_or_gap':'native check pending'}]
  write(self.d/'case-plan.json',self.plan)
  check(self.r,True)
 def test_partial_executable_gate(self):
  self.batch['all_executable_required']=True;write(self.r/'batch.json',self.batch)
  with self.assertRaisesRegex(ValueError,'executable artifact'):check(self.r,True)
 def test_lean_return_rejects_generated_media(self):
  self.batch['lean_return_required']=True;write(self.r/'batch.json',self.batch)
  (self.d/'diagnostic.webm').write_bytes(b'not for git')
  with self.assertRaisesRegex(ValueError,'Generated binary/media'):check(self.r,True)
 def test_bad_actor(self):
  self.plan['actor']='wrong';write(self.d/'case-plan.json',self.plan)
  with self.assertRaisesRegex(ValueError,'scope'):check(self.r,True)
 def test_unqualified_case_id(self):
  self.plan['cases'][0]['case_id']='baseline';write(self.d/'case-plan.json',self.plan)
  with self.assertRaisesRegex(ValueError,'case ID'):check(self.r,True)
 def test_broken_comparison(self):
  self.plan['comparisons']=[{'case_ids':['absent','other']}];write(self.d/'case-plan.json',self.plan)
  with self.assertRaisesRegex(ValueError,'comparison'):check(self.r,True)
 def test_fake_ready_requires_implementation(self):
  self.result['status']='ready';write(self.d/'result.json',self.result)
  with self.assertRaisesRegex(ValueError,'executable'):check(self.r,True)
 def ready(self):
  (self.d/'runner.py').write_text('print("offline fixture")\n')
  write(self.d/'config.json',{'law_id':'L1','actor':'driver','supported_case_ids':[self.aid+'__a']})
  write(self.d/'construction.json',{'cell_id':'C1','actor':'driver','entrypoint':'runner.py','files':[{'path':'runner.py','content':(self.d/'runner.py').read_text()}],'measurement_plan':{},'recording_description':{'channels':[{'name':'pose'}]},'static_checks':[],'termination_rules':{},'mechanisms':[]})
  write(self.d/'proposals/cases.json',{'cell_id':'C1','actor':'driver','status':'draft','sweep_specs':[],'cases':[{'case_id':self.aid+'__a','target_law_id':'L1','target_type':'boundary_probe','rationale':'fixture','variable_assignments':{},'unresolved_judgment_calls':[],'recording_description':{}}]})
  (self.d/'tests').mkdir();(self.d/'tests/test_fixture.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_fixture(self):self.assertTrue(True)\n')
  (self.d/'test.log').write_text('fixture passed')
  self.result.update(status='ready',tests=[{'command':'fixture','exit_code':0,'log':'test.log','sha256':sha(self.d/'test.log')}]);write(self.d/'result.json',self.result)
 def test_ready_complete_and_missing_channel(self):
  self.ready();check(self.r,True)
  c=read(self.d/'construction.json');c['recording_description']['channels']=[];write(self.d/'construction.json',c)
  with self.assertRaisesRegex(ValueError,'capture'):check(self.r,True)
 def test_source_term_requires_measured_evidence_mapping(self):
  self.ready()
  original=read(self.r/'inputs'/self.aid/'assignment.json')
  original['source_observation_terms']=[{'term':'drv.turning','note':'left turn'}]
  write(self.r/'inputs'/self.aid/'assignment.json',original)
  self.batch['assignments'][self.aid]['input_sha256']=sha(self.r/'inputs'/self.aid/'assignment.json')
  self.batch['frozen_files']={k:v for k,v in tree(self.r).items() if k!='batch.json' and not k.startswith('work/')}
  self.batch['source_observation_mapping_required']=True
  write(self.r/'batch.json',self.batch)
  self.result['input_sha256']=self.batch['assignments'][self.aid]['input_sha256']
  write(self.d/'result.json',self.result)
  self.plan['sources'][0]['sha256']=self.result['input_sha256']
  write(self.d/'case-plan.json',self.plan)
  with self.assertRaisesRegex(ValueError,'evidence mapping'):check(self.r,True)
  self.plan['source_observation_mapping']={'drv.turning':{'evidence':'Measured heading and route transition','channels':['pose'],'source_refs':[]}}
  write(self.d/'case-plan.json',self.plan)
  check(self.r,True)
 def test_changed_frozen_input(self):
  write(self.r/'inputs'/self.aid/'assignment.json',{})
  with self.assertRaisesRegex(ValueError,'frozen'):check(self.r,True)
 def test_stale_acknowledgement(self):
  self.result['applied_update']=1;write(self.d/'result.json',self.result)
  with self.assertRaisesRegex(ValueError,'update'):check(self.r,True)
 def test_update_pause_resume_and_restart(self):
  for version,action in [(2,'pause-affected'),(3,'continue'),(4,'resume')]:
   write(self.r/f'updates/{version:03d}.json',{'batch_id':'batch','version':version,'action':action,'assignments':[self.aid]})
   self.batch['update_version']=version;write(self.r/'batch.json',self.batch)
   expected=[] if action=='resume' else [self.aid]
   self.assertEqual(state(self.r)['paused_assignments'],expected)
   self.assertEqual(state(self.r)['paused_assignments'],expected)
 def test_update_unknown_scope(self):
  write(self.r/'updates/002.json',{'batch_id':'batch','version':2,'action':'pause-affected','assignments':['foreign']})
  with self.assertRaisesRegex(ValueError,'unassigned'):state(self.r)
 def test_static_checker_does_not_execute_runner(self):
  self.ready();marker=self.r/'executed'
  (self.d/'runner.py').write_text(f'open({str(marker)!r},"w").write("bad")\n')
  c=read(self.d/'construction.json');c['files'][0]['content']=(self.d/'runner.py').read_text();write(self.d/'construction.json',c)
  check(self.r,True);self.assertFalse(marker.exists())
 def test_publisher_explicit_staging_and_baseline(self):
  # A local bare remote exercises fetch/push without network or user config changes.
  import shutil
  shutil.rmtree(self.r/'work')
  subprocess.run(['git','init','-q',str(self.r)],check=True)
  def git(*args):return subprocess.check_output(['git','-C',str(self.r),*args],text=True).strip()
  git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');git('checkout','-qb','main');git('add','.');git('commit','-qm','initial')
  remote=pathlib.Path(self.tmp.name)/'remote.git';subprocess.run(['git','init','--bare','-q',str(remote)],check=True);git('remote','add','origin',str(remote));git('push','-q','origin','main')
  (self.r/'START_HERE.md').write_text('changed instruction')
  notice=pathlib.Path(self.tmp.name)/'notice.json';write(notice,{'version':3,'batch_id':'batch','action':'continue','assignments':'all','instructions':'Apply clarified checks'})
  receipt=pathlib.Path(self.tmp.name)/'receipts'
  out=publish(self.r,notice,['START_HERE.md'],receipt,True)
  self.assertEqual(out['version'],3);self.assertTrue((self.r/'updates/manifests/002.json').exists());self.assertTrue((receipt/'batch/export-update-003.json').exists())
  (self.r/'unrelated.txt').write_text('unrelated')
  with self.assertRaisesRegex(ValueError,'Declare'):publish(self.r,notice,[],receipt)
