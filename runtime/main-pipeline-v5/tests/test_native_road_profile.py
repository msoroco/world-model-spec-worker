import hashlib,json,math,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from traffic_spec_adapter.native_road_profile import apply,derivative,sha

class NativeRoadProfileTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);r=self.root
  r.joinpath('road.xodr').write_text('<OpenDRIVE><road length="1500"><planView><geometry x="0" y="0" hdg="0"><line/></geometry></planView><elevationProfile><elevation s="0" a="-56" b=".08" c="0" d="0"/><elevation s="650" a="-4" b=".08" c="-.0004" d="0"/><elevation s="850" a="-4" b="-.08" c="0" d="0"/></elevationProfile></road></OpenDRIVE>')
  def elevation(s):return -4+.08*(s-650) if s<650 else -4-.08*(s-850) if s>850 else -.0004*(s-750)**2
  samples=[]
  for s in range(450,1051,10):
   grade=.08 if s<650 else -.08 if s>850 else -.0008*(s-750)
   for lane in (-1,1):samples.append({'s_m':s,'lane_id':lane,'native_waypoint_m':[s,6 if lane==-1 else -6,elevation(s)],'native_rotation_deg':{'pitch':math.degrees(grade*(1 if lane==-1 else -1))},'all_surface_hits':[{'position_m':[s,0,elevation(s)]}]})
  self.write('native_hill_surface_survey.json',{'native_map_sha256':sha(r/'road.xodr'),'surface_samples':samples});r.joinpath('runner.py').write_text('original instrumentation');self.write('construction.json',{'files':[{'path':'runner.py','content':'original instrumentation'}]});self.write('result.json',{'completion':{'binding':{}}})
  self.packet={'schema':'native-straight-road-profile-v1','map_sha256':sha(r/'road.xodr'),'survey_sha256':sha(r/'native_hill_surface_survey.json'),'instrumentation_sha256':sha(r/'runner.py'),'half_road_width_m':12,'grade_patch_length_m':2,'crest_ridge_mesh_width_m':.25};self.write('native_road_profile.json',self.packet)
  self.telemetry=[{'frame':10,'time_s':.05,'native_road_profile':{'frame':10,'time_s':.05,'s_m':730,'native_z_before_after_m':[elevation(729.75),elevation(730.25)],'map_sha256':sha(r/'road.xodr')}}]
 def tearDown(self):self.temp.cleanup()
 def write(self,n,v):self.root.joinpath(n).write_text(json.dumps(v))
 def project(self):
  regions=[{'id':1,'kind':'roadway'}];polygons={}
  with patch('batch_pipeline.completion.verify'):receipt=apply(self.root,self.telemetry,regions,polygons)
  return receipt,regions,polygons
 def test_local_grade_patches_and_ridge_preserve_unknown_global_grade(self):
  receipt,regions,polygons=self.project();self.assertNotIn('grade',regions[0]);self.assertEqual(len(receipt['grade_patches']),300);self.assertEqual(receipt['physical_crests'][0]['station_m'],750);self.assertIsNone(receipt['physical_crests'][0]['legal_near_extent']);self.assertTrue(all(x['maximum_spatial_grade_error_ratio']<=.0008 for x in receipt['grade_patches']))
 def test_missing_frame_or_contradictory_local_slope_rejected(self):
  self.telemetry[0]['native_road_profile']['native_z_before_after_m']=[0,10]
  with self.assertRaisesRegex(ValueError,'slope'):self.project()
 def test_topmost_surface_contradiction_rejected(self):
  v=json.loads((self.root/'native_hill_surface_survey.json').read_text());v['surface_samples'][0]['all_surface_hits'].append({'position_m':[450,0,100]});self.write('native_hill_surface_survey.json',v);self.packet['survey_sha256']=sha(self.root/'native_hill_surface_survey.json');self.write('native_road_profile.json',self.packet)
  with self.assertRaisesRegex(ValueError,'topmost'):self.project()
 def test_changed_instrumentation_rejected(self):
  (self.root/'runner.py').write_text('changed')
  with self.assertRaisesRegex(ValueError,'provenance'):self.project()
