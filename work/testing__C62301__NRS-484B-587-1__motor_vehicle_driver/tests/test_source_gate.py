import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from package_spec import AID
from access import construct,CASES
class AccessGateTests(unittest.TestCase):
 def site(self,suffix):
  direction,indicated,visible=CASES[suffix]
  y=0 if indicated else 10
  pts=[{'point_id':'entry','direction':'entry','y_min_m':-1,'y_max_m':1,'device_id':'e','device_source':'official-e','erected':True,'notice_visible':visible if direction=='entry' else True},{'point_id':'exit','direction':'exit','y_min_m':-1,'y_max_m':1,'device_id':'x','device_source':'official-x','erected':True,'notice_visible':visible if direction=='exit' else True}]
  start,end=(-10,10) if direction=='entry' else (10,-10)
  return {'assignment_id':AID,'case_id':AID+'__'+suffix,'source_kind':'original_native_access_survey','reviewed_original_native_site':True,'source_id':'synthetic','map_name':'synthetic','map_sha256':'a'*64,'authority_source':'authority','highway_source':'highway','boundary_source':'boundary','official_notice_source':'official','driver_actor_id':'driver','public_highway':True,'controlled_access_determination':True,'authority_designated_devices':True,'boundary_x_m':0,'indicated_points':pts,'requested_direction':direction,'requested_indicated':indicated,'requested_notice_visible':visible,'target_point':{'direction':direction,'indicated':indicated,'notice_visible':visible,'point_id':direction if indicated else 'none','crossing_y_m':y,'source_ref':'official-point'},'native_spawn':{'source_id':'pose','blueprint_id':'vehicle.synthetic','pose_xyz_ypr':[start,y,0,0,0,0]},'trajectory':{'source_id':'route','points_xy':[[start,y],[start/2,y],[end,y]]}}
 def test_five_cases(self):
  for suffix in CASES:
   s=self.site(suffix);self.assertEqual(construct(s,s['case_id'])['direction'],CASES[suffix][0])
 def test_map_road_type_not_authority(self):
  s=self.site('indicated_entry');s['controlled_access_determination']=False
  with self.assertRaises(ValueError):construct(s,s['case_id'])
 def test_unerected_device_rejected(self):
  s=self.site('indicated_entry');s['indicated_points'][0]['erected']=False
  with self.assertRaises(ValueError):construct(s,s['case_id'])
 def test_wrong_crossing_rejected(self):
  s=self.site('unindicated_entry');s['target_point']['crossing_y_m']=0
  with self.assertRaises(ValueError):construct(s,s['case_id'])
