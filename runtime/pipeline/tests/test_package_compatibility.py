import unittest,tempfile,json,sys,hashlib,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from worker_exchange.common import read,write,sha,tree,digest
from worker_exchange.package_compatibility import check_receipts,CHECKS
class ProofTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.folder=self.root/'work/assignment';self.folder.mkdir(parents=True);self.fixture=self.root/'work/_shared/fixture';self.fixture.mkdir(parents=True);(self.fixture/'trace.jsonl').write_text('source')
  config={'required_atoms':['kin.speed']};self.files=[{'path':'config.json','content':json.dumps(config)},{'path':'analyze.py','content':'def measure(): pass'},{'path':'runner.py','content':'capture()'}]
  write(self.folder/'construction.json',{'files':self.files,'recording_description':{'channels':[{'name':'kin.speed'}]}})
  self.entry={'case_id':'case','construction':'construction.json','construction_sha256':sha(self.folder/'construction.json'),'measurement_procedure':{'entrypoint':'analyze.py'},'acquisition':{'kin.speed':{'entrypoint':'runner.py','method':'native velocity','evidence':['trace.jsonl']}},'compatibility':{'receipt':'proof.json','fixture':'work/_shared/fixture','log':'analysis.log'}}
  (self.folder/'analysis.log').write_text('');self.proof={'log_sha256':sha(self.folder/'analysis.log'),'format':'worker-package-compatibility','case_id':'case','passed':True,'checks':list(CHECKS),'construction_sha256':self.entry['construction_sha256'],'runtime_manifest_sha256':'runtime','fixture_sha256':digest(tree(self.fixture)),'analysis_sha256':hashlib.sha256(b'def measure(): pass').hexdigest()};
  source=self.fixture/'trace.jsonl'
  recipe=self.folder/'recipe.json'
  write(recipe,{'format':'worker-fixture-recipe','sources':[{'path':'case-source.json','source':str(source.relative_to(self.root)),'sha256':sha(source)}]})
  self.entry['fixture_recipe']=str(recipe.relative_to(self.root))
  self.entry['measurement_contract']='measurement.json'
  requirement={'requirement':'speed','source':'law'}
  write(self.folder/'case-plan.json',{'requirement_dispositions':[dict(requirement,status='selected_required')]})
  contract={'format':'worker-measurement-contract','requirements':[dict(requirement,disposition_index=0,output_key='speed',method='measure',value_type='number',kind='measured',inputs=['case-source.json'])],'negative':{'remove':['case-source.json'],'error_contains':'Missing required source: case-source.json'}}
  write(self.folder/'measurement.json',contract)
  (self.folder/'negative.log').write_text(contract['negative']['error_contains'])
  self.entry['negative']={'log':'negative.log'}
  self.proof.update(candidate_id='primary',checks=list(CHECKS|{'selected_measurements','negative_case_source'}),fixture_sha256=digest({'case-source.json':sha(source)}),fixture_recipe_sha256=sha(recipe),measurement_contract_sha256=sha(self.folder/'measurement.json'),measurement_keys=['speed'],measurement_examples={'speed':{'method':'measure','value':1.0,'sources':{'case-source.json':sha(source)}}},negative_removed='case-source.json',negative_error_contains=contract['negative']['error_contains'],negative_log_sha256=sha(self.folder/'negative.log'))
  from worker_exchange import fixture_generator
  self.proof['fixture_generator_sha256']=sha(Path(fixture_generator.__file__))
  self.save();self.manifest={'runtime_manifest_sha256':'runtime','cases':[self.entry]}
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
  with self.assertRaisesRegex(ValueError,'source missing/changed'):check_receipts(self.root,self.folder,self.manifest)
 def test_missing_acquisition(self):
  self.entry['acquisition']={}
  with self.assertRaisesRegex(ValueError,'acquisition'):check_receipts(self.root,self.folder,self.manifest)
 def test_missing_downstream_stage(self):
  self.proof['checks'].remove('native_validation');self.save()
  with self.assertRaisesRegex(ValueError,'Incomplete'):check_receipts(self.root,self.folder,self.manifest)
 def test_stale_analysis(self):
  self.proof['analysis_sha256']='old';self.save()
  with self.assertRaisesRegex(ValueError,'analysis changed'):check_receipts(self.root,self.folder,self.manifest)

 def test_retired_format_rejected(self):
  self.proof['format']='worker-package-compatibility-v2';self.save()
  with self.assertRaisesRegex(ValueError,'Incomplete'):check_receipts(self.root,self.folder,self.manifest)
 def test_recipe_cannot_inherit_retained_example(self):
  path=self.root/self.entry['fixture_recipe'];recipe=read(path);recipe['base']='runtime/retained-speed';write(path,recipe)
  from worker_exchange.fixture_recipe import inspect
  with self.assertRaisesRegex(ValueError,'explicitly inventory'):inspect(self.root,path)
 def test_recipe_cannot_supply_outputs(self):
  path=self.root/self.entry['fixture_recipe'];recipe=read(path);recipe['sources'][0]['path']='result.json';write(path,recipe)
  from worker_exchange.fixture_recipe import inspect
  with self.assertRaisesRegex(ValueError,'cannot supply'):inspect(self.root,path)

class GeneratedFixtures(unittest.TestCase):
 def test_portable_text_recipe_generates_reproducible_video(self):
  from worker_exchange.fixture_recipe import materialize
  from worker_exchange.media import audit
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'work/a/diagnostic.json'
   spec={'files':{'trace.jsonl':'{"frame":1}\n'},'graphs':[{'path':'capture/native/base.pkl','attributes':{'frame':1},'nodes':[{'id':'ego','attributes':{'sem_class':'vehicle.tesla.model3'}}],'edges':[]}],
         'videos':[{'path':'raw.mkv','frames':9,'width':32,'height':24,'fps':20,'color':'black'}]}
   write(source,spec)
   recipe=root/'work/a/recipe.json'
   write(recipe,{'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json','source':'work/a/diagnostic.json','sha256':sha(source)}],
                 'generator':{'source':'work/a/diagnostic.json','sha256':sha(source)}})
   first=materialize(root,recipe,root/'.runtime-work/one')
   second=materialize(root,recipe,root/'.runtime-work/two')
   self.assertEqual(first['fixture_sha256'],second['fixture_sha256'])
   self.assertTrue(audit(root/'.runtime-work/one/raw.mkv',9)['passed'])
   from traffic_spec_adapter.adapter import load_graph
   self.assertEqual(load_graph(root/'.runtime-work/one/capture/native/base.pkl').graph['frame'],1)
   write(source,dict(spec,files={'result.json':'{}'}))
   with self.assertRaisesRegex(ValueError,'source missing/changed'):materialize(root,recipe,root/'.runtime-work/stale')

 def test_generator_rejects_outputs_and_path_escape(self):
  from worker_exchange.fixture_generator import inspect
  for path in ('../outside','result.json','config.json'):
   with self.subTest(path=path),self.assertRaises(ValueError):
    inspect({'files':{path:'bad'},'graphs':[],'videos':[]})

class ExactCaseIntegration(unittest.TestCase):
 @unittest.skipUnless(__import__('os').environ.get('SCENARIO_WORKER_FIXTURE_REPO'),
                      'Set SCENARIO_WORKER_FIXTURE_REPO and SCENARIO_WORKER_VALIDATOR for the exact-case CPU integration')
 def test_actual_exported_processing_chain(self):
  import os,subprocess
  repo=Path(os.environ['SCENARIO_WORKER_FIXTURE_REPO']).resolve()
  validator=Path(os.environ['SCENARIO_WORKER_VALIDATOR']).resolve()
  frozen_runtime=tree(repo/'runtime')
  manifest=next((repo/'work').glob('*/execution-manifest.json'))
  case=read(manifest)['cases'][0]['case_id']
  (repo/'.runtime-work').mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=repo/'.runtime-work',prefix='integration-test-') as temporary:
   output=Path(temporary)/'processed';env=dict(os.environ);env.pop('PYTHONPATH',None)
   command=[sys.executable,'runtime.py','compatibility','--manifest',str(manifest),
            '--case',case,'--output',str(output),'--library',str(repo/'runtime/library'),
            '--validator',str(validator)]
   result=subprocess.run(command,cwd=repo,env=env,capture_output=True,text=True,timeout=300)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   proof=read(output/'compatibility.json')
   self.assertTrue(CHECKS|{'selected_measurements','negative_case_source'} <= set(proof['checks']))
   self.assertTrue(read(output/'final-decode.json')['passed'])
   self.assertTrue((output/'converted/trace.json').is_file())
   self.assertEqual(tree(repo/'runtime'),frozen_runtime)
