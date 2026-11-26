"""Build exact 600-frame passenger versus merchandise taxi proposals."""
import hashlib
import json
import copy
from pathlib import Path
from taxi_loading import check_config, measure

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
PREFIX = BASE.name
CAMERAS = [
    {'name':'overview','width':1920,'height':1080,'fps':20,'fov_deg':90,
     'location_xyz_m':[20,-12,35],'rotation_pyr_deg':[-45,0,135]},
    {'name':'approach','width':1280,'height':720,'fps':20,'fov_deg':85,
     'location_xyz_m':[0,-20,8],'rotation_pyr_deg':[-15,0,90]},
    {'name':'curb_reference','width':1280,'height':720,'fps':20,'fov_deg':80,
     'location_xyz_m':[14,13,8],'rotation_pyr_deg':[-15,0,225]},
    {'name':'driver_reference','width':1280,'height':720,'fps':20,'fov_deg':85,
     'location_xyz_m':[1,0,1.5],'rotation_pyr_deg':[0,0,0]},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')


def main():
    road = (SOURCE/'taxi-road.xodr').read_text()
    runner = (SOURCE/'runner.py').read_text()
    meter = (SOURCE/'taxi_loading.py').read_text()
    finalizer = (SOURCE/'finalize_original.py').read_text()
    cases = []
    for suffix, activity in (('probe_a','passenger_loading'),
                             ('probe_b','merchandise_loading')):
        case = PREFIX+'__'+suffix
        rows = []
        for i in range(600):
            active = 160 <= i < 400
            rows.append({'frame':i,'time_s':(i+1)/20,
                         'source_kind':'authored_native_request',
                         'requested_taxi_identity':True,
                         'requested_stand_location':'outside_designated_stand',
                         'requested_center_xy_m':[5.25,10],
                         'requested_speed_mps':0,
                         'requested_door_open':active,
                         'requested_occupant_count':2 if activity == 'merchandise_loading' or i < 400 else 3,
                         'requested_activity':activity if active else 'no_activity',
                         'original_native_observed':False})
        if measure(rows,'authored_native_request')['requested_activity'] != activity:
            raise ValueError('Activity contrast differs')
        config = {'case_id':case,'law_id':'LVMC-11-60-040','cell_id':'C394327',
                  'actor':'taxi_driver','duration_s':30,'rate_hz':20,'frames':600,
                  'road_sha256':sha(SOURCE/'taxi-road.xodr'),
                  'requested_activity':activity,'requested_activity_window_frames':[160,400],
                  'designation_source_required':True,
                  'other_regulations_review_required':True,
                  'cameras':CAMERAS,'physical_completion':False,'legal_verdict':None}
        check_config(config, road)
        track = ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n'
                        for row in rows)
        test = '''import copy\nimport json\nimport unittest\nfrom pathlib import Path\nfrom taxi_loading import check_config,read_and_measure\n\nclass ExactTaxi(unittest.TestCase):\n def setUp(self):self.config=json.loads(Path('config.json').read_text())\n def test_scope(self):\n  r=check_config(self.config,Path('taxi-road.xodr').read_text())\n  self.assertEqual(r['frames'],600)\n  self.assertFalse(r['actual_activity_observed'])\n def test_activity(self):\n  r=read_and_measure('requested-track.jsonl','authored_native_request')\n  self.assertEqual(r['requested_activity'],self.config['requested_activity'])\n  self.assertEqual(r['active_frames'],240)\n def test_negative(self):\n  for key,value in [('frames',599),('designation_source_required',False),('physical_completion',True)]:\n   cfg=copy.deepcopy(self.config);cfg[key]=value\n   with self.assertRaises(ValueError):check_config(cfg,Path('taxi-road.xodr').read_text())\n  with self.assertRaises(ValueError):read_and_measure('requested-track.jsonl','original_native')\n'''
        construction = {'case_id':case,'law_id':'LVMC-11-60-040',
                        'cell_id':'C394327','actor':'taxi_driver',
                        'entrypoint':'runner.py',
                        'files':[{'path':'runner.py','content':runner},
                                 {'path':'taxi_loading.py','content':meter},
                                 {'path':'finalize_original.py','content':finalizer},
                                 {'path':'taxi-road.xodr','content':road},
                                 {'path':'requested-track.jsonl','content':track},
                                 {'path':'config.json','content':json.dumps(config,indent=2)+'\n'},
                                 {'path':'tests/test_offline.py','content':test}],
                        'recording_description':{
                            'duration_s':30,'rate_hz':20,
                            'source_cameras':[c['name'] for c in CAMERAS],
                            'taxi_stand_designation_source_required':True,
                            'actual_passenger_or_merchandise_activity_required':True,
                            'other_stopping_regulations_review_required':True,
                            'legal_verdict':None},
                        'status':'draft_cpu_offline_only'}
        path = BASE/'draft-native'/suffix/'construction.json'
        write(path, construction)
        fallback_config = copy.deepcopy(config)
        fallback_config['candidate_id'] = 'curb_visibility_fallback'
        fallback_config['cameras'][2]['location_xyz_m'] = [8, 11, 5]
        check_config(fallback_config, road)
        fallback = copy.deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(fallback_config, indent=2) + '\n'
        fallback['candidate_id'] = 'curb_visibility_fallback'
        fallback['status'] = 'draft_cpu_offline_only'
        fallback_path = BASE/'draft-native'/suffix/'curb_visibility_fallback-construction.json'
        write(fallback_path, fallback)
        cases.append({'case_id':case,'construction':str(path.relative_to(BASE)),
                      'construction_sha256':sha(path),
                      'candidates':[{'id':'curb_visibility_fallback',
                        'construction':str(fallback_path.relative_to(BASE)),
                        'construction_sha256':sha(fallback_path),
                        'trigger':{'source':'original curb_reference.mkv and participant review',
                          'metric':'visible loading subject and taxi door during active window',
                          'failure_condition':'complete original capture has obscured loading subject or door'},
                        'changed_knobs':['curb_reference camera location from [14,13,8] to [8,11,5] metres; actor control and timing fixed']}],
                      'candidate_risk':{'status':'physical',
                        'reason':'Original taxi identity, stand designation and participant loading activity need Native review.'}})
        fallback_log = SOURCE/('proof-'+suffix.replace('_','-')+'-fallback.log')
        if fallback_log.is_file():
            cases[-1]['candidates'][0]['offline'] = {
                'exit_code': 0,
                'construction_sha256': sha(fallback_path),
                'log': str(fallback_log.relative_to(BASE)),
                'log_sha256': sha(fallback_log)}
        write(SOURCE/('request-meter-'+suffix+'.json'),
              measure(rows,'authored_native_request'))
    write(BASE/'draft-native-manifest.json',{
        'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':PREFIX,'status':'draft_not_selected','cases':cases,
        'original_native_observed':False,'delivery_ready':False})


if __name__ == '__main__':
    main()
