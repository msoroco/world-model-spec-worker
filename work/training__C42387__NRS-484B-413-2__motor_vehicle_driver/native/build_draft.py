"""Build 100-foot business turn signaling draft requests."""
import hashlib
import json
from pathlib import Path
from signal_distance import check_config,measure

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name
CAMERAS=[
 {'name':'overview','width':1920,'height':1080,'fps':20,'fov_deg':90,
  'location_xyz_m':[85,25,35],'rotation_pyr_deg':[-45,0,315]},
 {'name':'approach','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[50,-10,8],'rotation_pyr_deg':[-15,0,0]},
 {'name':'turn_reference','width':1280,'height':720,'fps':20,'fov_deg':80,
  'location_xyz_m':[110,10,8],'rotation_pyr_deg':[-15,0,225]},
 {'name':'driver_reference','width':1280,'height':720,'fps':20,'fov_deg':85,
  'location_xyz_m':[1,0,1.5],'rotation_pyr_deg':[0,0,0]},
]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def main():
 road=(SOURCE/'business-turn-road.xodr').read_text()
 runner=(SOURCE/'runner.py').read_text();meter=(SOURCE/'signal_distance.py').read_text()
 cases=[]
 for suffix,onset,expected in (('probe_a',260,True),('probe_b',320,False)):
  case=PREFIX+'__'+suffix
  rows=[]
  for i in range(600):
   d=round(i*0.25,4)
   rows.append({'frame':i,'time_s':(i+1)/20,
    'source_kind':'authored_native_request',
    'path_length_m':d,'ego_center_xy_m':[min(d,100),-max(0,d-100)],
    'ego_speed_mps':5,'right_signal_on':i>=onset,
    'hand_signal_on':False,'right_turn_begins':i==400,
    'weather':'clear','original_native_observed':False})
  if measure(rows,'authored_native_request')['requested_meets_100_feet']!=expected:
   raise ValueError('Requested continuous distance differs')
  config={'case_id':case,'law_id':'NRS-484B-413-2','cell_id':'C42387',
   'actor':'motor_vehicle_driver','district':'business',
   'duration_s':30,'rate_hz':20,'frames':600,'road_sha256':sha(SOURCE/'business-turn-road.xodr'),
   'requested_signal_onset_frame':onset,
   'district_source_required':True,'signal_state_source_required':True,
   'original_path_source_required':True,'course_change_source_required':True,
   'cameras':CAMERAS,'physical_completion':False,'legal_verdict':None}
  check_config(config,road)
  track=''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rows)
  test='''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom signal_distance import check_config,read_and_measure\n\nclass ExactSignal(unittest.TestCase):\n def setUp(self):self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  r=check_config(self.config,Path('business-turn-road.xodr').read_text())\n  self.assertEqual(r['frames'],600)\n def test_distance(self):\n  r=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(r['requested_meets_100_feet'],self.config['requested_signal_onset_frame']==260)\n def test_negative(self):\n  for key,value in [('frames',599),('district_source_required',False),('physical_completion',True)]:\n   cfg=copy.deepcopy(self.config);cfg[key]=value\n   with self.assertRaises(ValueError):check_config(cfg,Path('business-turn-road.xodr').read_text())\n  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')\n'''
  construction={'case_id':case,'law_id':'NRS-484B-413-2',
   'cell_id':'C42387','actor':'motor_vehicle_driver','entrypoint':'runner.py',
   'files':[{'path':'runner.py','content':runner},
    {'path':'signal_distance.py','content':meter},
    {'path':'business-turn-road.xodr','content':road},
    {'path':'requested-track.jsonl','content':track},
    {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
    {'path':'tests/test_offline.py','content':test}],
   'recording_description':{'duration_s':30,'rate_hz':20,
    'source_cameras':[c['name'] for c in CAMERAS],
    'district_source_required':True,'original_signal_and_path_required':True,
    'right_turn_source_required':True,'legal_verdict':None},
   'status':'draft_cpu_offline_only'}
  path=BASE/'draft-native'/suffix/'construction.json';write(path,construction)
  cases.append({'case_id':case,'construction':str(path.relative_to(BASE)),
   'construction_sha256':sha(path),'candidates':[],
   'candidate_risk':{'status':'physical','reason':
    'Original business-district status, turn path, signal continuity and camera visibility require Native review.'}})
  write(SOURCE/('request-meter-'+suffix+'.json'),measure(rows,'authored_native_request'))
 write(BASE/'draft-native-manifest.json',{
  'format':'worker-unselected-draft-construction-manifest-v1',
  'assignment_id':PREFIX,'status':'draft_not_selected','cases':cases,
  'original_native_observed':False,'delivery_ready':False})


if __name__=='__main__':main()
