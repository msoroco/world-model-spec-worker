"""Bind two exact 600-frame sloped-curb parked lamp source proposals."""
import hashlib
import json
from pathlib import Path
from parked_lamps import check_config,measure

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name
CAMERAS=[
 {'name':'overview','width':1920,'height':1080,'fps':20,'fov_deg':90,
  'location_xyz_m':[15,-20,30],'rotation_pyr_deg':[-45,0,90]},
 {'name':'approach','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[6,-20,7],'rotation_pyr_deg':[-15,0,90]},
 {'name':'reference_corner','width':1280,'height':720,'fps':20,'fov_deg':75,
  'location_xyz_m':[16,18,4],'rotation_pyr_deg':[0,0,220]},
 {'name':'driver_reference','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[1,0,1.5],'rotation_pyr_deg':[0,0,0]},
]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def request(state):
 return [{'frame':i,'time_s':(i+1)/20,'source_kind':'authored_native_request',
          'ego_center_xyz_m':[4.85,0,2.4], 'ego_speed_mps':0,
          'requested_headlamp_lit':True,'requested_beam_state':state,
          'requested_parking_lane_id':-2,'requested_curb_offset_m':0.15,
          'original_native_observed':False} for i in range(600)]

def main():
 runner=(SOURCE/'runner.py').read_text()
 meter=(SOURCE/'parked_lamps.py').read_text()
 road=(SOURCE/'sloped-curb-road.xodr').read_text()
 cases=[]
 for suffix,state in (('probe_a','low_beam'),('probe_b','high_beam')):
  case_id=PREFIX+'__'+suffix
  rows=request(state)
  measured=measure(rows,'authored_native_request')
  if measured['requested_beam_state']!=state:raise ValueError('Request differs')
  config={'case_id':case_id,'law_id':'NRS-484D-165-4','cell_id':'C276263',
          'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'frames':600,
          'road_sha256':sha(SOURCE/'sloped-curb-road.xodr'),
          'requested_beam_state':state,'original_beam_pixel_review_required':True,
          'original_parking_context_required':True,'cameras':CAMERAS,
          'physical_completion':False,'legal_verdict':None}
  check_config(config,road)
  track=''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)
  test='''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom parked_lamps import check_config,read_and_measure\n\nclass ExactLamp(unittest.TestCase):\n def setUp(self):self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  result=check_config(self.config,Path('sloped-curb-road.xodr').read_text())\n  self.assertEqual(result['frames'],600)\n  self.assertFalse(result['beam_depressed_or_dimmed_observed'])\n def test_request(self):\n  result=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(result['requested_beam_state'],self.config['requested_beam_state'])\n  self.assertFalse(result['actual_parking_observed'])\n def test_negative(self):\n  for key,value in [('frames',599),('physical_completion',True),('original_beam_pixel_review_required',False)]:\n   cfg=copy.deepcopy(self.config);cfg[key]=value\n   with self.assertRaises(ValueError):check_config(cfg,Path('sloped-curb-road.xodr').read_text())\n  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')\n'''
  construction={'case_id':case_id,'law_id':'NRS-484D-165-4',
                'cell_id':'C276263','actor':'motor_vehicle_driver',
                'entrypoint':'runner.py',
                'files':[{'path':'runner.py','content':runner},
                         {'path':'parked_lamps.py','content':meter},
                         {'path':'sloped-curb-road.xodr','content':road},
                         {'path':'requested-track.jsonl','content':track},
                         {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
                         {'path':'tests/test_offline.py','content':test}],
                'recording_description':{'duration_s':30,'rate_hz':20,
                    'source_cameras':[c['name'] for c in CAMERAS],
                    'original_headlamp_light_state_readback_required':True,
                    'pixel_beam_elevation_and_intensity_review_required':True,
                    'actual_parking_context_and_road_grade_unverified':True,
                    'legal_verdict':None},
                'status':'draft_cpu_offline_only'}
  path=BASE/'draft-native'/suffix/'construction.json';write(path,construction)
  cases.append({'case_id':case_id,'construction':str(path.relative_to(BASE)),
                'construction_sha256':sha(path),'candidates':[],
                'candidate_risk':{'status':'physical',
                   'reason':'Actual curb parking, low/high requested beam aim and brightness, camera exposure and Native OpenDRIVE grade require original source review.'}})
  write(SOURCE/('request-meter-'+suffix+'.json'),measured)
 write(BASE/'draft-native-manifest.json',{
   'format':'worker-unselected-draft-construction-manifest-v1',
   'assignment_id':PREFIX,'status':'draft_not_selected','cases':cases,
   'original_native_observed':False,'delivery_ready':False})

if __name__=='__main__':main()
