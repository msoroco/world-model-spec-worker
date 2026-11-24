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
 {'name':'reference_corner','width':1280,'height':720,'fps':20,'fov_deg':80,
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
 for suffix,release,expected,approach_kind,officer_direction in (
    ('probe_a',360,True,'authorized_emergency',False),
    ('probe_b',240,False,'authorized_emergency',False),
    ('exception_1_1',240,False,'authorized_emergency',False),
    ('exception_1_2',240,False,'authorized_emergency',True),
    ('official_1',360,True,'regulatory_official',False),
    ('official_2',240,False,'regulatory_official',False)):
  case=PREFIX+'__'+suffix
  candidates=[]
  for candidate, approach_start, approach_step, overview_fov in (
    ('primary',-30,0.1,90),('fallback1',-35,0.115,90),
    ('fallback2',-30,0.1,105)):
   rows=[]
   for i in range(600):
    moving=i>=release
    ego_y=0 if not moving else round((i-release)*0.02,4)
    emergency_y=round(approach_start+i*approach_step,4)
    rows.append({'frame':i,'time_s':(i+1)/20,
      'source_kind':'authored_native_request',
      'ego_center_xy_m':[5.25,ego_y],
      'ego_body_xy_m':[[x,round(ego_y+y,4)] for x in (4.25,6.25) for y in (-2.25,2.25)],
      'ego_speed_mps':0 if not moving else 0.4,
      'emergency_center_xy_m':[1.75,emergency_y],
      'emergency_body_xy_m':[[x,round(emergency_y+y,4)] for x in (0.75,2.75) for y in (-2.25,2.25)],
      'requested_approach_kind':approach_kind,
      'requested_emergency_authorized':approach_kind=='authorized_emergency',
      'requested_regulatory_official':approach_kind=='regulatory_official',
      'requested_flashing_lights':True,
      'requested_officer_direction':officer_direction,
      'original_native_observed':False})
   if measure(rows,'authored_native_request')['requested_waits_through_whole_body_passage']!=expected:
    raise ValueError('Requested whole-body passage contrast differs')
   cameras=[dict(c, fov_deg=overview_fov if c['name']=='overview' else c['fov_deg'],
                 pose_strategy='fixed_world_aim_at_approach') for c in CAMERAS]
   config={'case_id':case,'law_id':'NRS-484B-267-1c','cell_id':'C405647',
    'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'frames':600,
    'road_sha256':sha(SOURCE/'emergency-road.xodr'),
    'requested_release_frame':release,
    'approach_kind':approach_kind,
    'officer_direction_request':officer_direction,
    'candidate_id':candidate,'requested_emergency_start_y_m':approach_start,
    'requested_emergency_step_y_m_per_frame':approach_step,
    'supported_case_ids':[PREFIX+'__'+name for name in
      ('probe_a','probe_b','exception_1_1','exception_1_2','official_1','official_2')],
    'required_atoms':['rel.same_direction','rel.surface_gap','kin.position','rel.occupies'],
    'source_packets':[],
    'emergency_authorization_source_required':True,
    'qualifying_flashes_source_required':True,
    'officer_direction_source_required':True,
    'original_passage_source_required':True,
    'cameras':cameras,'physical_completion':False,'legal_verdict':None}
   check_config(config,road)
   track=''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in rows)
   test='''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom emergency_wait import check_config,read_and_measure\n\nclass ExactEmergency(unittest.TestCase):\n def setUp(self):self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  r=check_config(self.config,Path('emergency-road.xodr').read_text())\n  self.assertEqual(r['frames'],600)\n  self.assertFalse(r['actual_passing_observed'])\n def test_passage(self):\n  r=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(r['requested_waits_through_whole_body_passage'],self.config['requested_release_frame']==360)\n def test_negative(self):\n  for key,value in [('frames',599),('qualifying_flashes_source_required',False),('physical_completion',True)]:\n   cfg=copy.deepcopy(self.config);cfg[key]=value\n   with self.assertRaises(ValueError):check_config(cfg,Path('emergency-road.xodr').read_text())\n  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')\n'''
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
      'channels':[{'name':name,'unit':'structured','sampling_rate_hz':20,
                   'method':'Original Native actor, body, map and camera frame join',
                   'time_window':'all 600 frames','reference_frame':'original Native frame',
                   'uncertainty':'50 ms frame bracket; source qualification separate'}
                  for name in ('drv.responding_emergency','drv.stopped','rel.occupies',
                               'kin.position','rel.ahead_behind_in_lane','drv.cleared_line',
                               'kin.velocity','approach_kind','qualifying_lamp_pixels',
                               'officer_direction','subject_body','emergency_body',
                               'video_frame_join')],
      'qualifying_flashing_lights_source_required':True,
      'officer_direction_source_required':True,
      'emergency_vehicle_passage_source_required':True,'legal_verdict':None},
   'measurement_plan':{'source':'observed-actors.jsonl and video_frames.jsonl',
     'method':'Compute first ego release and full emergency rear versus ego front passage from original bodies; source authority and lamp qualification require separate review',
     'legal_verdict':None},
   'static_checks':['exact law, cell, actor, branch and 600-frame identity',
                    'four source cameras and map lanes',
                    'whole-body passage source required'],
   'termination_rules':['capture 600 joined Native frames or fail without acceptance'],
   'mechanisms':['Native actor pose controller','four original FFV1 camera streams',
                 'source-bound saved passage measurement'],
   'status':'draft_cpu_offline_only'}
   path=BASE/'draft-native'/suffix/candidate/'construction.json';write(path,construction)
   candidates.append({'id':candidate,'construction':str(path.relative_to(BASE)),
    'construction_sha256':sha(path)})
   write(SOURCE/('request-meter-'+suffix+'-'+candidate+'.json'),measure(rows,'authored_native_request'))
  cases.append({'case_id':case,'construction':candidates[0]['construction'],
   'construction_sha256':candidates[0]['construction_sha256'],'candidates':candidates[1:],
   'candidate_risk':{'status':'physical','reason':
     'Full-body passage timing and camera coverage need Native readback; fallback1 shifts approach timing and fallback2 widens overview field of view.'}})
 write(BASE/'draft-native-manifest.json',{
   'format':'worker-unselected-draft-construction-manifest-v1',
   'assignment_id':PREFIX,'status':'draft_not_selected','cases':cases,
   'original_native_observed':False,'delivery_ready':False})


if __name__=='__main__':main()
