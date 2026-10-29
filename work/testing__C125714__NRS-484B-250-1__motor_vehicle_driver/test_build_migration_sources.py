"""CPU-only structural and retained-source tests for AST migration002."""
import ast, importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=Path(__file__).with_name('build_migration_sources.py');SP=importlib.util.spec_from_file_location('migration_builder002',P);m=importlib.util.module_from_spec(SP);SP.loader.exec_module(m)
class MigrationSourceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.originals=[]
  for p in sorted((ROOT/'.runtime-work/update002/originals').glob('*/construction-*.json')):
   c=json.loads(p.read_text());files={f['path']:f['content'] for f in c['files']};cfg=json.loads(files['config.json']);runner,prep=m.migrate_runner(files['runner.py']);cls.originals.append((c,cfg,runner,prep))
 def test_all236_capture_only_and_preparation_syntax(self):
  self.assertEqual(len(self.originals),236)
  for c,cfg,runner,prep in self.originals:
   with self.subTest(case=c['case_id']):
    compile(runner,'runner.py','exec');compile(prep,'analyze.py','exec');self.assertTrue(m.verify_runner(runner)['context_before_cleanup']);self.assertNotIn('from analyze import finalize',runner);self.assertNotIn('import compose_four_views',runner)
 def test_retained_exact_packet_inputs_preserved(self):
  for c,cfg,runner,prep in self.originals:
   with self.subTest(case=c['case_id']),tempfile.TemporaryDirectory() as t:
    root=Path(t);(root/'config.json').write_text(json.dumps(cfg))
    # Find recipe by actual assignment/case identity; no current package mutation.
    aid='__'.join(c['case_id'].split('__')[:4]);current=json.loads((ROOT/'work'/aid/'execution-manifest.json').read_text());entry=next(e for e in current['cases'] if e['case_id']==c['case_id']);recipe=json.loads((ROOT/entry['fixture_recipe']).read_text())
    for item in recipe['additions']:
     p=root/item['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/item['source']).read_bytes())
    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()};ns={};exec(prep,ns);result=ns['prepare_saved'](root)
    self.assertIn(result['status'],('already_prepared','not_required'));self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
 def test_surface_context_keeps_enrichment(self):
  c,cfg,runner,prep=next(row for row in self.originals if row[1]['law_id']=='NRS-484B-127-1')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'config.json').write_text(json.dumps(cfg));(root/'acquisition-context.json').write_text(json.dumps({'surface_authoring':{'ice_or_snow':False,'source':'captured actual authoring snapshot'}}));ns={};exec(prep,ns);ns['prepare_saved'](root);context=json.loads((root/'surface_context.json').read_text());self.assertIn('surface_authoring',context);self.assertEqual(context['surface_authoring']['source'],'captured actual authoring snapshot')
 def test_native600_calibration_is_actual_saved_packet(self):
  c,cfg,runner,prep=next(row for row in self.originals if row[1]['law_id']=='NRS-484B-600-1a')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'config.json').write_text(json.dumps(cfg));(root/'acquisition-context.json').write_text(json.dumps({'native_map_name':'original-map','cal':{'samples':[{'longitudinal_range_m':42}]}}));cal={'samples':[{'longitudinal_range_m':42}],'visibility_m':42,'source':'actual sealed source'};(root/'environment_calibration.json').write_text(json.dumps(cal));(root/'road.xodr').write_text('<OpenDRIVE><road><lanes><laneSection><right><lane id="-1" type="driving"><width a="7"/></lane><lane id="-2" type="shoulder"><width a="3"/></lane></right></laneSection></lanes></road></OpenDRIVE>')
   rows=[{'frame':1,'speed_mps':5}];other=[{'frame':1,'other_speed_mps':4,'separation_m':10,'traffic_actor_inventory':[],'weather':{'wetness':0,'fog_density':2,'precipitation':0},'sight_ray_hit_count':0}];(root/'trace.jsonl').write_text(json.dumps(rows[0])+'\n');(root/'other_motion.jsonl').write_text(json.dumps(other[0])+'\n');ns={};exec(prep,ns);ns['prepare_saved'](root);packet=json.loads((root/'case_observation.json').read_text());self.assertEqual(packet['visibility_calibration'],cal)
 def test_missing_capture_context_rejects_new_derivation(self):
  c,cfg,runner,prep=next(row for row in self.originals if row[1]['law_id']=='NRS-484B-600-1e')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'config.json').write_text(json.dumps(cfg));ns={};exec(prep,ns)
   with self.assertRaisesRegex(ValueError,'Missing required source: acquisition-context.json:'):ns['prepare_saved'](root)
 def test_idempotent_migration_refuses_capture_only_source(self):
  with self.assertRaisesRegex(ValueError,'already migrated'):m.migrate_runner(self.originals[0][2])
if __name__=='__main__':unittest.main()
