import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from package_spec import AID
from right_pass import construct,VARIANTS
class PavedEdgeSourceTests(unittest.TestCase):
 def site(self,suffix):
  fit,passed,off=VARIANTS[suffix];hi=8 if fit else 4;sections=[{'station_m':s,'source_kind':'surveyed_original_native_pavement','source_ref':'synthetic-section','connected_drivable_route':True,'paved_y_bounds_m':[-5,hi]} for s in range(-30,31,5)]
  return {'assignment_id':AID,'case_id':AID+'__'+suffix,'source_kind':'original_native_map_geometry','reviewed_original_native_site':True,'source_id':'synthetic','map_name':'synthetic','map_sha256':'a'*64,'paved_surface_source':'synthetic-surface','paved_boundary_source':'synthetic-edge','connected_route_source':'synthetic-route','driver_actor_id':'driver','overtaken_actor_source':'synthetic-actor','public_highway':True,'paved_surface_classified':True,'adjacent_surface_classified':True,'requested_zero_clearance_paved_fit':fit,'requested_right_pass':passed,'requested_off_pavement':off,'road_frame':{'source_id':'synthetic-frame','origin_xy':[0,0],'station_axis_xy':[1,0],'left_axis_xy':[0,1]},'cross_sections':sections,'ego_body_half_width_m':1,'overtaken_right_edge_m':3,'variant_controls':{'source_id':'synthetic-control','ego_speed_mps':8 if passed else 4,'target_speed_mps':5,'ego_target_lateral_m':hi+1 if off else 4 if passed else 2},'native_spawn':{r:{'source_id':'synthetic-'+r,'blueprint_id':'vehicle.synthetic','pose_xyz_ypr':[0,0,0,0,0,0]} for r in ('ego','target')}}
 def test_four_exact_source_cases(self):
  for suffix in VARIANTS:
   x=self.site(suffix);self.assertEqual(construct(x,x['case_id'])['expected_pass'],VARIANTS[suffix][1])
 def test_map_lane_type_not_pavement(self):
  x=self.site('wide_on_pavement');x['paved_surface_classified']=False
  with self.assertRaises(ValueError):construct(x,x['case_id'])
 def test_unconnected_corridor_rejected(self):
  x=self.site('narrow_off_pavement');x['cross_sections'][4]['connected_drivable_route']=False
  with self.assertRaises(ValueError):construct(x,x['case_id'])
