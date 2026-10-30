"""Independent mathematical and original-frame join checks for partition-two laws."""
import importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'runtime/main-pipeline-v1/scenario_pipeline'))
IDS=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids']
def load(aid):
 path=ROOT/'work'/aid/'analyze.py';s=importlib.util.spec_from_file_location('law_'+aid,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def packet(aid,name):
 spec=json.loads((ROOT/'work'/aid/'package-spec.json').read_text());return next(c['fixture']['case_observation.json'] for c in spec['cases'] if c['name']==name)

class Measurements(unittest.TestCase):
 def test_entry_order_is_measured_not_asserted(self):
  m=load(IDS[0]);self.assertGreater(m.earlier_entry(packet(IDS[0],'precedence'))['time_difference_s'],0);self.assertLess(m.earlier_entry(packet(IDS[0],'other_later'))['time_difference_s'],0)
 def test_one_way_uses_velocity_not_heading(self):
  m=load(IDS[3]);self.assertTrue(all(v>0 for v in m.direction_projection(packet(IDS[3],'designated'))['signed_projections_mps']));self.assertTrue(all(v<0 for v in m.direction_projection(packet(IDS[3],'opposed_reverse'))['signed_projections_mps']))
 def test_divider_checks_body_against_prohibited_geometry(self):
  m=load(IDS[2]);self.assertEqual(m.turn_trajectory(packet(IDS[2],'opening'))['median_body_overlap_frames'],[]);self.assertTrue(m.turn_trajectory(packet(IDS[2],'closed_divider'))['median_body_overlap_frames'])
 def test_divider_relations_preserve_distinct_observations(self):
  m=load(IDS[2]);rows=m.divider_relations(packet(IDS[2],'closed_divider'))['samples'];self.assertTrue(any(r['partial_xy_overlap'] for r in rows));self.assertTrue(all('whole_body_xy_within' in r and 'body_bottom_z_m' in r and 'body_top_z_m' in r and 'divider_top_z_m' in r for r in rows));self.assertNotEqual(rows[0]['body_lateral_min_y_m'],rows[-1]['body_lateral_min_y_m'])
 def test_distinct_90_degree_left_turn(self):
  aid='testing__C80909__NRS-484B-227-1__motor_vehicle_driver';m=load(aid);self.assertAlmostEqual(m.turn_shape(packet(aid,'opening_aligned'))['actual_velocity_direction_change_deg'],90);self.assertEqual(m.turn_trajectory(packet(aid,'opening_aligned'))['median_body_overlap_frames'],[]);self.assertTrue(m.turn_trajectory(packet(aid,'opening_displaced'))['median_body_overlap_frames'])
 def test_visibility_reads_original_image_calibration(self):
  m=load(IDS[4]);value,sources=m.read_calibrated_visibility(ROOT/'runtime/main-pipeline-v1/fixtures/retained-speed');self.assertEqual(value['visibility_m'],400);self.assertEqual(value['distance_kind'],'sampled_lower_bound');self.assertEqual(len(sources),11);self.assertEqual(len(value['original_contrast_samples']),5)
 def test_visibility_rejects_changed_original_image(self):
  import tempfile
  m=load(IDS[4]);cal=json.loads((ROOT/'runtime/main-pipeline-v1/fixtures/retained-speed/environment_calibration.json').read_text())
  with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work/tmp') as tmp:
   p=Path(tmp);(p/'environment_calibration.json').write_text(json.dumps(cal));image=p/cal['samples'][0]['rgb']['path'];image.parent.mkdir(parents=True);image.write_bytes(b'corrupt diagnostic fixture image')
   with self.assertRaisesRegex(ValueError,'Calibration original image hash mismatch'):m.read_calibrated_visibility(p)
 def test_highway_width_is_source_specific(self):
  m=load(IDS[4]);self.assertEqual(m.road_conditions(packet(IDS[4],'reference'))['highway_width_m'],10);self.assertEqual(m.road_conditions(packet(IDS[4],'narrower'))['highway_width_m'],8)
 def test_signal_distance_continuity_contrasts(self):
  m=load(IDS[5]);self.assertTrue(m.indicator_continuity(packet(IDS[5],'continuous100'))['continuous_api_on']);self.assertFalse(m.indicator_continuity(packet(IDS[5],'short80'))['continuous_api_on']);self.assertFalse(m.indicator_continuity(packet(IDS[5],'interrupted'))['continuous_api_on'])
 def test_300ft_is_not_100ft(self):
  aid='testing__C412593__NRS-484B-413-2__motor_vehicle_driver';m=load(aid);p=packet(aid,'other_area_continuous');self.assertEqual(m.approach_path(p)['threshold_ft'],300);self.assertAlmostEqual(m.approach_path(p)['threshold_m'],91.44)
 def test_all_source_frames_join_retained_originals(self):
  aids=IDS+[b['assignment_id'] for b in json.loads((ROOT/'work'/IDS[0]/'additional-bindings.json').read_text())]
  def visit(v):
   if isinstance(v,dict):
    for k,x in v.items():
     if k in ['frame','ego_clearance_frame','other_clearance_frame','turn_onset_frame']:self.assertIn(x,[21714,21715,21716])
     elif k=='original_frames':self.assertTrue(set(x)<={21714,21715,21716})
     else:visit(x)
   elif isinstance(v,list):
    for x in v:visit(x)
  for aid in aids:
   for c in json.loads((ROOT/'work'/aid/'package-spec.json').read_text())['cases']:visit(c['fixture']['case_observation.json'])
if __name__=='__main__':unittest.main()
