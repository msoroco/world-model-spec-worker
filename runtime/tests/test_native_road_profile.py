import json,math,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from traffic_spec_adapter import native_road_profile as m
sha=m.sha
class NativeRoadProfileTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);r=self.root
  r.joinpath('road.xodr').write_text('<OpenDRIVE><road id="1" junction="-1" length="1500"><planView><geometry s="0" x="0" y="0" hdg="0" length="1500"><line/></geometry></planView><elevationProfile><elevation s="0" a="-56" b=".08" c="0" d="0"/><elevation s="650" a="-4" b=".08" c="-.0004" d="0"/><elevation s="850" a="-4" b="-.08" c="0" d="0"/></elevationProfile><lanes><laneSection s="0"><left><lane id="1" type="driving"><width sOffset="0" a="12" b="0" c="0" d="0"/></lane></left><right><lane id="-1" type="driving"><width sOffset="0" a="12" b="0" c="0" d="0"/></lane></right></laneSection></lanes></road></OpenDRIVE>')
  self.builder='carla.OpendriveGenerationParameters(vertex_distance=.25,wall_height=0,additional_width=0)';r.joinpath('runner.py').write_text(self.builder);self.write('construction.json',{'entrypoint':'python runner.py','files':[{'path':'runner.py','content':self.builder}]});self.write('result.json',{'completion':{'binding':{}}});self.telemetry=[];self.rebind()
 def tearDown(self):self.temp.cleanup()
 def write(self,n,v):self.root.joinpath(n).write_text(json.dumps(v))
 def rebind(self):
  road=ET.parse(self.root/'road.xodr').getroot().find('road');elev=road.findall('./elevationProfile/elevation');centers,_=m._lane_layout(road);samples=[]
  for s in range(450,1051,10):
   e=max((x for x in elev if float(x.get('s'))<=s),key=lambda x:float(x.get('s')));d=s-float(e.get('s'));z=sum(float(e.get(k))*d**i for i,k in enumerate('abcd'))
   for lane,cy in centers.items():
    xy=m._xy(road,s,-cy);samples.append({'s_m':s,'lane_id':lane,'native_waypoint_m':[xy[0],-xy[1],z],'native_rotation_deg':{'pitch':math.degrees(m.derivative(e,s)*(1 if lane<0 else -1))},'all_surface_hits':[{'position_m':[xy[0],-xy[1],z]}]})
  self.write('native_hill_surface_survey.json',{'native_map_sha256':sha(self.root/'road.xodr'),'surface_samples':samples});self.packet={'map_sha256':sha(self.root/'road.xodr'),'survey_sha256':sha(self.root/'native_hill_surface_survey.json'),'instrumentation_sha256':sha(self.root/'runner.py'),'crest_ridge_mesh_width_m':.25};self.write('native_road_profile.json',self.packet)
 def project(self):
  regions=[{'id':5,'kind':'centre_line'},{'id':1,'kind':'roadway'}];polygons={}
  with patch('traffic_spec_adapter.inventory_observations.Evidence') as reader:
   reader.return_value.expected={};reader.return_value.path.side_effect=lambda name:self.root/name
   receipt=m.apply(self.root,self.telemetry,regions,polygons)
  return receipt,regions,polygons
 def test_no_region_grade_or_midpoint_patch(self):
  receipt,regions,_=self.project();self.assertNotIn('grade_samples',receipt);self.assertEqual(len(regions),3);self.assertEqual(regions[-1]['id'],6);self.assertEqual(regions[0]['kind'],'centre_line');self.assertEqual(receipt['physical_crests'][0]['station_m'],750);self.assertIsNone(receipt['physical_crests'][0]['legal_near_extent']);self.assertTrue(all('grade'not in r and 'curvature'not in r for r in regions))
 def test_original_generator_resolution_without_optional_packet(self):
  (self.root/'native_road_profile.json').unlink();self.assertEqual(self.project()[0]['physical_crests'][0]['mesh_representation_width_m'],.25)
 def test_curved_crest_is_on_verified_surface(self):
  tree=ET.parse(self.root/'road.xodr');g=tree.find('./road/planView/geometry');g.remove(g.find('line'));ET.SubElement(g,'arc',curvature='.001');tree.write(self.root/'road.xodr');self.rebind();receipt,regs,polys=self.project();self.assertEqual(regs[-1]['kind'],'crest');self.assertGreater(polys[6].area,5.9);self.assertLess(polys[6].area,6.1)
 def test_topmost_surface_contradiction_rejected(self):
  v=json.loads((self.root/'native_hill_surface_survey.json').read_text());v['surface_samples'][0]['all_surface_hits'].append({'position_m':[450,0,100]});self.write('native_hill_surface_survey.json',v);self.packet['survey_sha256']=sha(self.root/'native_hill_surface_survey.json');self.write('native_road_profile.json',self.packet)
  with self.assertRaisesRegex(ValueError,'topmost'):self.project()
 def test_changed_generator_rejected(self):
  (self.root/'runner.py').write_text('changed')
  with self.assertRaisesRegex(ValueError,'generator'):self.project()
 def test_wrong_survey_map_rejected(self):
  v=json.loads((self.root/'native_hill_surface_survey.json').read_text());v['native_map_sha256']='0'*64;self.write('native_hill_surface_survey.json',v)
  with self.assertRaisesRegex(ValueError,'another source map'):self.project()
 def test_incomplete_cross_section_rejected(self):
  v=json.loads((self.root/'native_hill_surface_survey.json').read_text());v['surface_samples'].pop();self.write('native_hill_surface_survey.json',v);self.packet['survey_sha256']=sha(self.root/'native_hill_surface_survey.json');self.write('native_road_profile.json',self.packet)
  with self.assertRaisesRegex(ValueError,'cross-section'):self.project()
