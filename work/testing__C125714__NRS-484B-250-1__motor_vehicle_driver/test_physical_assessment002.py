"""CPU-only outcome and source-schema tests for migration002 strategies."""
import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('physical002',Path(__file__).with_name('physical_assessment002.py'))
physical=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(physical)
class AssessmentTests(unittest.TestCase):
 def cases(self):
  for manifest in sorted((ROOT/'work').glob('*/execution-manifest.json')):
   for entry in json.loads(manifest.read_text())['cases']:
    bundle=json.loads((manifest.parent/entry['construction']).read_text());cfg=json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json'))
    if cfg['law_id'].startswith('NRS-484B-400-'):continue
    recipe=json.loads((ROOT/entry['fixture_recipe']).read_text());base=ROOT/recipe['base'];texts={name:(base/name).read_text() for name in ['trace.jsonl','video_frames.jsonl']};texts.update({a['path']:(ROOT/a['source']).read_text() for a in recipe['additions']});texts['config.json']=json.dumps(cfg)
    yield entry['case_id'],cfg,texts
 def put(self,root,texts):
  for name,text in texts.items():
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
 def test_all_non400_case_outcomes(self):
  total=0
  for cid,cfg,texts in self.cases():
   for kind,expected in [('complete_motion','met'),('incomplete_motion','not_met'),('missing_evidence','unverified')]:
    with self.subTest(case=cid,kind=kind), tempfile.TemporaryDirectory() as t:
     root=Path(t);self.put(root,texts);physical.make_motion_fixture(root,cfg,kind);result=physical.assess_physical(root,cfg,[{'matched':True}]);check=result['physical_checks']['maneuver']
     self.assertEqual(check['status'],expected,check);self.assertEqual(result['maneuver_completed'],expected=='met');self.assertTrue(check['sources']);self.assertTrue(check['method'])
     if kind=='complete_motion':self.assertTrue(result['realized_observables']);self.assertEqual(result['physical_checks']['setup']['status'],'not_met')
     total+=1
  self.assertEqual(total,684)
 def test_fixture_label_cannot_make_stationary_complete(self):
  cid,cfg,texts=next(self.cases())
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.put(root,texts);physical.make_motion_fixture(root,cfg,'incomplete_motion');(root/'fixture-provenance.json').write_text(json.dumps({'kind':'complete_motion','provenance_kind':'native'}))
   self.assertEqual(physical.assess_physical(root,cfg)['physical_checks']['maneuver']['status'],'not_met')
 def test_timestamp_corruption_is_unverified(self):
  cid,cfg,texts=next(self.cases())
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.put(root,texts);physical.make_motion_fixture(root,cfg,'complete_motion');p=root/physical.default_descriptor(cfg)['motion_source'];rows=physical._rows(p);rows[1]['time_s']=999;p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   self.assertEqual(physical.assess_physical(root,cfg)['physical_checks']['maneuver']['status'],'unverified')
 def test_complete_capture_setup(self):
  cid,cfg,texts=next(self.cases());cfg=dict(cfg,duration_s=.15,rate_hz=20)
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.put(root,texts);(root/'config.json').write_text(json.dumps(cfg));physical.make_motion_fixture(root,cfg,'complete_motion')
   self.assertEqual(physical.assess_physical(root,cfg)['physical_checks']['setup']['status'],'met')
 def test_full_rotation_does_not_equal_reversal(self):
  cid,cfg,texts=next(c for c in self.cases() if c[1]['law_id']=='NRS-484B-407')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.put(root,texts);physical.make_motion_fixture(root,cfg,'complete_motion');p=root/'turn_history.jsonl';rows=physical._rows(p)
   for i,r in enumerate(rows):r['heading_deg']=i*180;r['cumulative_heading_change_deg']=i*180
   p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.assertEqual(physical.assess_physical(root,cfg)['physical_checks']['maneuver']['status'],'not_met')
 def test_left_turn_wrong_destination_is_not_complete(self):
  cid,cfg,texts=next(c for c in self.cases() if c[1]['cell_id']=='C80909')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.put(root,texts);physical.make_motion_fixture(root,cfg,'complete_motion');p=root/'body_history.jsonl';rows=physical._rows(p);rows[-1]['road_id']=2;p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   self.assertEqual(physical.assess_physical(root,cfg)['physical_checks']['maneuver']['status'],'not_met')
 def test_actual_subject_body_field_required(self):
  cid,cfg,texts=next(c for c in self.cases() if c[1]['law_id']=='NRS-484B-223-1b')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.put(root,texts);physical.make_motion_fixture(root,cfg,'complete_motion');p=root/'lane_history.jsonl';rows=physical._rows(p);rows[1].pop('subject_vertices_m');p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   self.assertEqual(physical.assess_physical(root,cfg)['physical_checks']['maneuver']['status'],'unverified')
 def test_tiny_progress_is_not_full_travel_milestone(self):
  cid,cfg,texts=next(c for c in self.cases() if c[1]['law_id']=='NRS-484B-600-1e')
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.put(root,texts);physical.make_motion_fixture(root,cfg,'complete_motion');p=root/'trace.jsonl';rows=physical._rows(p)
   for i,r in enumerate(rows):r['position_m']=[i*.1,1.75,0]
   p.write_text(''.join(json.dumps(r)+'\n' for r in rows));self.assertEqual(physical.assess_physical(root,cfg,[{'matched':True}])['physical_checks']['maneuver']['status'],'not_met')
if __name__=='__main__':unittest.main()
