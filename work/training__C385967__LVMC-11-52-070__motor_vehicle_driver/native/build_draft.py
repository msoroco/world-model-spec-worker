"""Build two exact 600-frame one-way angle-bay orientation proposals."""
import hashlib
import json
from pathlib import Path
from angle_park import check_config,measure

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name
CAMERAS=[
 {'name':'overview','width':1920,'height':1080,'fps':20,'fov_deg':90,
  'location_xyz_m':[20,-18,35],'rotation_pyr_deg':[-45,0,135]},
 {'name':'approach','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[0,-25,8],'rotation_pyr_deg':[-15,0,90]},
 {'name':'reference_corner','width':1280,'height':720,'fps':20,'fov_deg':80,
  'location_xyz_m':[15,10,8],'rotation_pyr_deg':[-15,0,225]},
 {'name':'driver_reference','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[1,0,1.5],'rotation_pyr_deg':[0,0,0]},
]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def main():
 road=(SOURCE/'angle-bay-road.xodr').read_text()
 runner=(SOURCE/'runner.py').read_text();meter=(SOURCE/'angle_park.py').read_text()
 cases=[]
 for suffix,yaw,expected in (('probe_a',45,'front_with_lawful_flow'),
                             ('probe_b',225,'front_against_lawful_flow')):
  case=PREFIX+'__'+suffix
  rows=[{'frame':i,'time_s':(i+1)/20,'source_kind':'authored_native_request',
         'ego_center_xy_m':[6.5,0],'ego_front_yaw_deg':yaw,
         'ego_speed_mps':0,'requested_parking_bay_id':'bay-901',
         'requested_activity':'parked','original_native_observed':False}
        for i in range(600)]
  if measure(rows,'authored_native_request')['direction']!=expected:
   raise ValueError('Authored orientation request differs')
  config={'case_id':case,'law_id':'LVMC-11-52-070','cell_id':'C385967',
          'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'frames':600,
          'road_sha256':sha(SOURCE/'angle-bay-road.xodr'),
          'requested_front_yaw_deg':yaw,'permission_source_required':True,
          'original_activity_source_required':True,'cameras':CAMERAS,
          'physical_completion':False,'legal_verdict':None}
  check_config(config,road)
  track=''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)
  test='''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom angle_park import check_config,read_and_measure\n\nclass ExactBay(unittest.TestCase):\n def setUp(self):self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  r=check_config(self.config,Path('angle-bay-road.xodr').read_text())\n  self.assertEqual(r['frames'],600)\n  self.assertFalse(r['engineer_permission_verified'])\n def test_direction(self):\n  r=read_and_measure('requested-track.jsonl','authored_native_request')\n  expected='front_with_lawful_flow' if self.config['requested_front_yaw_deg']==45 else 'front_against_lawful_flow'\n  self.assertEqual(r['direction'],expected)\n def test_negative(self):\n  for key,value in [('frames',599),('permission_source_required',False),('physical_completion',True)]:\n   cfg=copy.deepcopy(self.config);cfg[key]=value\n   with self.assertRaises(ValueError):check_config(cfg,Path('angle-bay-road.xodr').read_text())\n  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')\n'''
  construction={'case_id':case,'law_id':'LVMC-11-52-070',
                'cell_id':'C385967','actor':'motor_vehicle_driver',
                'entrypoint':'runner.py',
                'files':[{'path':'runner.py','content':runner},
                         {'path':'angle_park.py','content':meter},
                         {'path':'angle-bay-road.xodr','content':road},
                         {'path':'requested-track.jsonl','content':track},
                         {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
                         {'path':'tests/test_offline.py','content':test}],
                'recording_description':{'duration_s':30,'rate_hz':20,
                    'source_cameras':[c['name'] for c in CAMERAS],
                    'lawful_traffic_direction_source':'one-way road 1 heading north',
                    'city_engineer_permission_source_required':True,
                    'original_parking_activity_and_bay_footprint_required':True,
                    'legal_verdict':None},
                'status':'draft_cpu_offline_only'}
  path=BASE/'draft-native'/suffix/'construction.json';write(path,construction)
  cases.append({'case_id':case,'construction':str(path.relative_to(BASE)),
                'construction_sha256':sha(path),'candidates':[],
                'candidate_risk':{'status':'physical',
                 'reason':'Authored bay, actual sign indication, city permission, vehicle orientation and parking activity require Native source review.'}})
  write(SOURCE/('request-meter-'+suffix+'.json'),measure(rows,'authored_native_request'))
 write(BASE/'draft-native-manifest.json',{
   'format':'worker-unselected-draft-construction-manifest-v1',
   'assignment_id':PREFIX,'status':'draft_not_selected','cases':cases,
   'original_native_observed':False,'delivery_ready':False})

if __name__=='__main__':main()
