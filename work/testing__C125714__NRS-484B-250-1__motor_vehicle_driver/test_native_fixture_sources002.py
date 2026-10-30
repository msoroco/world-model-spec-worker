"""Fresh capture-only source -> selected saved preparation/analyzer, CPU only."""
import ast,hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OWN=Path(__file__).resolve().parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
builder=module('source_builder002',OWN/'build_migration_sources.py');physical=module('assessment002',OWN/'physical_assessment002.py');native=module('native_fixture_sources002',OWN/'native_fixture_sources002.py')
class FreshNativeSources(unittest.TestCase):
 def originals(self):
  for p in sorted((ROOT/'.runtime-work/update002/originals').glob('*/construction-*.json')):
   c=json.loads(p.read_text());files={f['path']:f['content'] for f in c['files']};cfg=json.loads(files['config.json']);yield c,files,cfg
 def inputs(self,cfg):
  aid='__'.join(cfg['selected_case_id'].split('__')[:4]);manifest=json.loads((ROOT/'work'/aid/'execution-manifest.json').read_text());entry=next(e for e in manifest['cases'] if e['case_id']==cfg['selected_case_id']);recipe=json.loads((ROOT/entry['fixture_recipe']).read_text());base=ROOT/recipe['base'];data={name:(base/name).read_bytes() for name in ['trace.jsonl','video_frames.jsonl','road.xodr','environment_calibration.json','surface_provenance.json','fixture-provenance.json','capture/evidence.jsonl']};data.update({a['path']:(ROOT/a['source']).read_bytes() for a in recipe['additions']})
  if cfg['law_id']=='NRS-484B-600-1a':
   cal=json.loads(data['environment_calibration.json'])
   for sample in cal['samples']:
    for channel in ('rgb','instance'):path=sample[channel]['path'];data[path]=(base/path).read_bytes()
  return data
 def test_all236_fresh_raw_derivation_and_analysis(self):
  failures=[];proofs=[]
  for c,files,cfg in self.originals():
   with self.subTest(case=c['case_id']),tempfile.TemporaryDirectory() as t:
    root=Path(t)
    for name,data in self.inputs(cfg).items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    for name,source in files.items():
     if name.endswith('.py') and not name.startswith('tests/'):
      p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
    (root/'config.json').write_text(json.dumps(cfg));runner,prep=builder.migrate_runner(files['runner.py'])
    if not cfg['law_id'].startswith('NRS-484B-400-'):physical.make_motion_fixture(root,cfg,'complete_motion')
    try:
     record=native.make_native_sources(root,cfg,prep)
     self.assertTrue(record['removed_before_seal']);self.assertTrue(all(not (root/name).exists() for name in record['derived_outputs']))
     # This is the saved phase after the modeled owner release. It uses the
     # exact selected preparation source, then the unchanged law finalizer.
     ns={'__name__':'diagnostic_saved_analysis','__file__':str(root/'analyze.py')};sys.path.insert(0,str(root))
     try:
      exec(files['analyze.py']+'\n'+prep,ns);ns['prepare_saved'](root);ns['finalize'](root,root/'analysis-report.json')
     finally:sys.path.remove(str(root))
     result=json.loads((root/'result.json').read_text());self.assertEqual(result['case_id'],c['case_id']);self.assertTrue((root/'analysis-report.json').is_file());proofs.append({'case_id':c['case_id'],'raw_sources':record['raw_source_hashes'],'derived_outputs':record['derived_outputs'],'passed':True})
    except Exception as e:
     failures.append({'case_id':c['case_id'],'error':str(e),'type':type(e).__name__});raise
  report={'cases':len(proofs),'failures':failures,'proofs':proofs,'source_sha256':hashlib.sha256((OWN/'native_fixture_sources002.py').read_bytes()).hexdigest(),'software_fixture_only':True,'physical_acceptance_claimed':False};(OWN/'migration-fresh-native-source-proof.json').write_text(json.dumps(report,indent=2)+'\n');self.assertEqual(len(proofs),236)
 def test_413_authoring_preserves_complete_and_incomplete_readbacks(self):
  count=0
  for c,files,cfg in self.originals():
   if cfg['law_id']!='NRS-484B-413-2':continue
   for kind in ('complete_motion','incomplete_motion'):
    with self.subTest(case=c['case_id'],kind=kind),tempfile.TemporaryDirectory() as t:
     root=Path(t)
     for name,data in self.inputs(cfg).items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
     (root/'config.json').write_text(json.dumps(cfg));physical.make_motion_fixture(root,cfg,kind)
     before=[(r.get('lane_id'),r.get('road_id')) for r in native._rows(root/'body_history.jsonl')]
     prep=builder.migrate_runner(files['runner.py'])[1];native.make_native_sources(root,cfg,prep,strict=False)
     after=[(r.get('lane_id'),r.get('road_id')) for r in native._rows(root/'body_history.jsonl')]
     for prior,current in zip(before,after):
      for original,value in zip(prior,current):
       if original is not None:self.assertEqual(original,value)
     self.assertEqual(physical.assess_physical(root,cfg)['physical_checks']['maneuver']['status'],'met' if kind=='complete_motion' else 'not_met');count+=1
  self.assertGreater(count,0)
 def test_227_zero_motion_is_preserved(self):
  c,files,cfg=next(x for x in self.originals() if x[2]['law_id'].startswith('NRS-484B-227'))
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for name,data in self.inputs(cfg).items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
   (root/'config.json').write_text(json.dumps(cfg));physical.make_motion_fixture(root,cfg,'incomplete_motion')
   rows=native._rows(root/'trace.jsonl')
   for row in rows:row['velocity_mps']=[0,0,0];row['speed_mps']=0
   (root/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));before=(root/'trace.jsonl').read_bytes()
   native.make_native_sources(root,cfg,builder.migrate_runner(files['runner.py'])[1],strict=False)
   self.assertEqual((root/'trace.jsonl').read_bytes(),before)
 def test_real_capture_authoring_refused(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'never rewrite a real capture'):native.make_native_sources(Path(t),{'law_id':'NRS-484B-600-1e'})
if __name__=='__main__':unittest.main()
