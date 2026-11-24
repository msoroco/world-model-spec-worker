"""Bind two 30-second, 600-frame C329610 left-turn speed requests."""
import hashlib
import json
import math
from pathlib import Path
from speed_turn import MPH_PER_MPS,check_config,measure

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name
CAMERAS=[
 {'name':'overview','width':1920,'height':1080,'fps':20,'fov_deg':90,
  'location_xyz_m':[-8,-35,45],'rotation_pyr_deg':[-55,0,90]},
 {'name':'approach','width':1280,'height':720,'fps':20,'fov_deg':80,
  'location_xyz_m':[-70,-12,10],'rotation_pyr_deg':[-10,0,0]},
 {'name':'reference_corner','width':1280,'height':720,'fps':20,'fov_deg':90,
  'location_xyz_m':[20,20,12],'rotation_pyr_deg':[-20,0,225]},
 {'name':'driver_reference','width':1280,'height':720,'fps':20,'fov_deg':90,
  'location_xyz_m':[1,0,1.5],'rotation_pyr_deg':[0,0,0]},
]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def request(target_mph):
 high=target_mph/MPH_PER_MPS
 distance=0;out=[];arc_len=8.75*math.pi/2
 for i in range(600):
  t=(i+1)/20
  speed=high if t<=4 else high+(10-high)*(t-4)/4 if t<=8 else 10
  distance+=speed/20
  if distance<423:
   road_id=1;x=-430+distance;y=-1.75;velocity=[speed,0,0]
  elif distance<423+arc_len:
   road_id=13;theta=-math.pi/2+(distance-423)/8.75
   x=-7+8.75*math.cos(theta);y=7+8.75*math.sin(theta)
   velocity=[-speed*math.sin(theta),speed*math.cos(theta),0]
  else:
   road_id=4;x=1.75;y=7+(distance-423-arc_len);velocity=[0,speed,0]
  out.append({'frame':i,'time_s':t,'source_kind':'authored_native_request',
              'ego_center_xyz_m':[x,y,0],'ego_velocity_xyz_mps':velocity,
              'road_id':road_id,'lane_id':-1,
              'requested_speed_mph':target_mph,
              'original_native_observed':False})
 return out

def main():
 road=(SOURCE/'road.xodr').read_text();runner=(SOURCE/'runner.py').read_text()
 meter=(SOURCE/'speed_turn.py').read_text();cases=[]
 for suffix,mph in (('probe_a',75),('probe_b',85)):
  case=PREFIX+'__'+suffix;rows=request(mph)
  proof=measure(rows,'authored_native_request')
  if (proof['frames_greater_than_80_mph']>0)!=(mph>80):
   raise ValueError('Authored speed contrast differs')
  config={'case_id':case,'law_id':'NRS-484B-600-1e',
          'cell_id':'C329610','actor':'motor_vehicle_driver',
          'duration_s':30,'rate_hz':20,'frames':600,
          'road_sha256':sha(SOURCE/'road.xodr'),
          'road_source_provenance':
            'work/training__C329610__NRS-484B-413-2__motor_vehicle_driver/native-constructions/scene.xodr; approach extended to 423 m, junction/left-turn arc held fixed',
          'requested_speed_mph':mph,'cameras':CAMERAS,
          'physical_completion':False,'legal_verdict':None}
  check_config(config,road)
  track=''.join(json.dumps(x,separators=(',',':'),allow_nan=False)+'\n' for x in rows)
  test='''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom speed_turn import check_config,read_and_measure\n\nclass ExactSpeed(unittest.TestCase):\n def setUp(self):self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  check=check_config(self.config,Path('road.xodr').read_text())\n  self.assertEqual(check['frames'],600)\n  self.assertFalse(check['original_speed_observed'])\n def test_request(self):\n  report=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(report['frames_greater_than_80_mph']>0,self.config['requested_speed_mph']>80)\n  self.assertEqual(report['route_road_ids'],[1,13,4])\n def test_negative(self):\n  for key,value in [('frames',599),('physical_completion',True),('cell_id','wrong')]:\n   config=copy.deepcopy(self.config);config[key]=value\n   with self.assertRaises(ValueError):check_config(config,Path('road.xodr').read_text())\n  lines=Path('requested-track.jsonl').read_text().splitlines()\n  Path('truncated-track.jsonl').write_text('\\n'.join(lines[:-1])+'\\n')\n  with self.assertRaises(ValueError):read_and_measure('truncated-track.jsonl','authored_native_request')\n'''
  construction={'case_id':case,'law_id':'NRS-484B-600-1e',
                'cell_id':'C329610','actor':'motor_vehicle_driver',
                'entrypoint':'runner.py',
                'files':[{'path':'runner.py','content':runner},
                         {'path':'speed_turn.py','content':meter},
                         {'path':'road.xodr','content':road},
                         {'path':'requested-track.jsonl','content':track},
                         {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
                         {'path':'tests/test_offline.py','content':test}],
                'recording_description':{'duration_s':30,'rate_hz':20,
                  'source_cameras':[c['name'] for c in CAMERAS],
                  'speed_source':'original Native velocity vector, not requested speed',
                  '80_mph_in_mps':80/MPH_PER_MPS,
                  'actual_motion_and_left_turn_unverified':True,
                  'legal_verdict':None},
                'status':'draft_cpu_offline_only'}
  path=BASE/'draft-native'/suffix/'construction.json';write(path,construction)
  cases.append({'case_id':case,'construction':str(path.relative_to(BASE)),
                'construction_sha256':sha(path),'candidates':[],
                'candidate_risk':{'status':'physical',
                  'reason':'Native vehicle may not sustain requested 85 mph and safely complete left turn; original velocity and camera readback required.'}})
  write(SOURCE/('request-meter-'+suffix+'.json'),proof)
 write(BASE/'draft-native-manifest.json',{
   'format':'worker-unselected-draft-construction-manifest-v1',
   'assignment_id':PREFIX,'status':'draft_not_selected','cases':cases,
   'original_native_observed':False,'delivery_ready':False})

if __name__=='__main__':main()
