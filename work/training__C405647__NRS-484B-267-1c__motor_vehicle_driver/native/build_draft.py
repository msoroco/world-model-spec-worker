"""Build exact emergency-passage wait and early-release draft requests."""
import hashlib
import json
from pathlib import Path
from emergency_wait import check_config,measure

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
PREFIX = BASE.name
CAMERAS = [
 {'name':'overview','width':1920,'height':1080,'fps':20,'fov_deg':90,
  'location_xyz_m':[20,-10,35],'rotation_pyr_deg':[-45,0,135]},
 {'name':'approach','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[0,-25,8],'rotation_pyr_deg':[-15,0,90]},
 {'name':'right_edge','width':1280,'height':720,'fps':20,'fov_deg':80,
  'location_xyz_m':[15,10,8],'rotation_pyr_deg':[-15,0,225]},
 {'name':'driver_reference','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[1,0,1.5],'rotation_pyr_deg':[0,0,0]},
]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def main():
 road=(SOURCE/'emergency-road.xodr').read_text()
 runner=(SOURCE/'runner.py').read_text()
 meter=(SOURCE/'emergency_wait.py').read_text()
 cases=[]
 for suffix,release,expected in (('probe_a',360,True),('probe_b',240,False)):
  case=PREFIX+'__'+suffix
  rows=[]
  for i in range(600):
   moving=i>=release
   rows.append({'frame':i,'time_s':(i+1)/20,
      'source_kind':'authored_native_request',
      'ego_center_xy_m':[5.25,0 if not moving else round((i-release)*0.02,4)],
      'ego_speed_mps':0 if not moving else 0.4,
      'emergency_center_xy_m':[1.75,round(-30+i*0.1,4)],
      'requested_emergency_authorized':True,
      'requested_flashing_lights':True,
      'requested_officer_direction':None,
      'original_native_observed':False})
  if measure(rows,'authored_native_request')['requested_waits_through_center_passage']!=expected:
   raise ValueError('Requested passage contrast differs')
  config={'case_id':case,'law_id':'NRS-484B-267-1c','cell_id':'C405647',
    'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'frames':600,
    'road_sha256':sha(SOURCE/'emergency-road.xodr'),
    'requested_release_frame':release,
    'emergency_authorization_source_required':True,
    'qualifying_flashes_source_required':True,
    'officer_direction_source_required':True,
    'original_passage_source_required':True,
    'cameras':CAMERAS,'physical_completion':False,'legal_verdict':None}
  check_config(config,road)
  track=''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rows)
  test='''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom emergency_wait import check_config,read_and_measure\n\nclass ExactEmergency(unittest.TestCase):\n def setUp(self):self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  r=check_config(self.config,Path('emergency-road.xodr').read_text())\n  self.assertEqual(r['frames'],600)\n  self.assertFalse(r['actual_passing_observed'])\n def test_passage(self):\n  r=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(r['requested_waits_through_center_passage'],self.config['requested_release_frame']==360)\n def test_negative(self):\n  for key,value in [('frames',599),('qualifying_flashes_source_required',False),('physical_completion',True)]:\n   cfg=copy.deepcopy(self.config);cfg[key]=value\n   with self.assertRaises(ValueError):check_config(cfg,Path('emergency-road.xodr').read_text())\n  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')\n'''
  construction={'case_id':case,'law_id':'NRS-484B-267-1c',
   'cell_id':'C405647','actor':'motor_vehicle_driver','entrypoint':'runner.py',
   'files':[{'path':'runner.py','content':runner},
            {'path':'emergency_wait.py','content':meter},
            {'path':'emergency-road.xodr','content':road},
            {'path':'requested-track.jsonl','content':track},
            {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
            {'path':'tests/test_offline.py','content':test}],
   'recording_description':{'duration_s':30,'rate_hz':20,
      'source_cameras':[c['name'] for c in CAMERAS],
      'qualifying_flashing_lights_source_required':True,
      'officer_direction_source_required':True,
      'emergency_vehicle_passage_source_required':True,'legal_verdict':None},
   'status':'draft_cpu_offline_only'}
  path=BASE/'draft-native'/suffix/'construction.json';write(path,construction)
  cases.append({'case_id':case,'construction':str(path.relative_to(BASE)),
   'construction_sha256':sha(path),'candidates':[],
   'candidate_risk':{'status':'physical','reason':
     'Original emergency authorization, qualifying flashes, officer direction, right-edge position and passage need Native review.'}})
  write(SOURCE/('request-meter-'+suffix+'.json'),measure(rows,'authored_native_request'))
 write(BASE/'draft-native-manifest.json',{
   'format':'worker-unselected-draft-construction-manifest-v1',
   'assignment_id':PREFIX,'status':'draft_not_selected','cases':cases,
   'original_native_observed':False,'delivery_ready':False})


if __name__=='__main__':main()
