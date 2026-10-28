"""Truthful raw projections, engineering geometry and original RGB byte tap."""
import io,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import execution
class Projections(unittest.TestCase):
 def setUp(self):
  p={'actor_id':1,'position_m':[0.,0.,0.],'heading_deg':0.,'velocity_mps':[3.,0.,0.],'speed_mps':3.,'vertices':[[-1.,-1.,0.],[1.,-1.,0.],[1.,1.,0.],[-1.,1.,0.]]}
  self.sample={'time_s':.05,'ego':p,'participants':[p,dict(p,actor_id=2)],'road':{'road_id':1,'lane_id':-1,'lane_width_m':3.5,'station_m':200.,'forward':[1.,0.]},'weather':{'wetness':0.,'fog_density':0.,'fog_distance':1000.},'devices':[],'lamps':0,'inside':[False,True],'distance_m':2.,'physical_dividers':[]}
  self.geometry={'intersection':[[0,0],[5,0],[5,5],[0,5]],'intersection_road_ids':[1,2],'participant_routes':[[1],[2]],'authored_context':{'test_assumption':True},'surface_reference':'road.xodr','surface_provenance':{'authored_surface':'fixture only'}}
 def test_all_mandatory_names_have_nonnull_projection(self):
  config=json.loads((ROOT/'config.json').read_text())
  for channel in config['cases'][0]['recording_description']['channels']:
   with self.subTest(atom=channel['name']):self.assertIsNotNone(execution.project(channel['name'],self.sample,[],self.geometry))
 def test_velocity_and_heading_not_controller_target(self):
  self.assertEqual(execution.project('kin.speed',self.sample,[],self.geometry),3.)
  direction=execution.project('drv.wrong_way',self.sample,[],self.geometry);self.assertEqual(direction['dot_product_mps'],3.)
  self.sample['ego']['velocity_mps']=[-2.,0.,0.]
  self.assertEqual(execution.project('drv.wrong_way',self.sample,[],self.geometry)['dot_product_mps'],-2.)
 def test_empty_control_inventory_is_evidence_not_fabricated_sign(self):
  value=execution.project('dev.regulatory_sign',self.sample,[],self.geometry);self.assertEqual(value['inventory'],[])
 def test_qualitative_raw_does_not_resolve_standard(self):
  value=execution.project('drv.sight_distance_adequate',self.sample,[],self.geometry);self.assertIn('unresolved',value['criterion']);self.assertNotIn('adequate',value)
 def test_original_optical_bytes_are_preserved(self):
  output=io.BytesIO();measurements=[];tap=execution.OpticalTap(output,2,2,measurements);tap.context={'time_s':0.,'carla_frame':10,'roi':[0,0,2,2]};raw=bytes([0,0,255,255])*4
  tap.write(raw);self.assertEqual(output.getvalue(),raw);self.assertAlmostEqual(measurements[0]['mean_luminance'],.2126*255);self.assertNotIn('flashing_confirmed',measurements[0])
 def test_wrong_rgb_dimensions_fail(self):
  tap=execution.OpticalTap(io.BytesIO(),2,2,[])
  with self.assertRaises(ValueError):tap.write(b'not a video frame')
 def test_event_brackets_do_not_assert_exact_equality(self):
  rows=[]
  for t,inside in [(0,[False,False]),(.05,[False,True]),(.1,[True,True])]:rows.append({'time_s':t,'inside':inside,'participants':[{'actor_id':1},{'actor_id':2}]})
  summary=execution.event_summary(rows);self.assertEqual(summary['entry_brackets_s']['1'],[.05,.1]);self.assertEqual(summary['entry_brackets_s']['2'],[0,.05])
