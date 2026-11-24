"""Independent exact comparison of emergency-passage draft requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
 manifest=json.loads((BASE/'draft-native-manifest.json').read_text())
 assert manifest['assignment_id']==PREFIX and manifest['status']=='draft_not_selected'
 assert [c['case_id'] for c in manifest['cases']]==[PREFIX+'__probe_a',PREFIX+'__probe_b']
 road=ET.fromstring((SOURCE/'emergency-road.xodr').read_text()).find('road')
 assert road.find('./planView/geometry/line') is not None
 assert {l.get('id'):l.get('type') for l in road.findall('./lanes/laneSection/right/lane')}=={
  '-1':'driving','-2':'driving','-3':'shoulder'}
 pair=[]
 for case in manifest['cases']:
  path=BASE/case['construction'];assert sha(path)==case['construction_sha256']
  bundle=json.loads(path.read_text())
  files={f['path']:f['content'] for f in bundle['files']}
  config=json.loads(files['config.json'])
  rows=[json.loads(s) for s in files['requested-track.jsonl'].splitlines()]
  assert len(rows)==600
  assert all(r['frame']==i and r['time_s']==(i+1)/20 for i,r in enumerate(rows))
  assert config['road_sha256']==sha(SOURCE/'emergency-road.xodr')
  assert config['physical_completion'] is False and config['legal_verdict'] is None
  assert all(config[k] is True for k in ('emergency_authorization_source_required',
   'qualifying_flashes_source_required','officer_direction_source_required',
   'original_passage_source_required'))
  assert len(config['cameras'])==4
  pair.append((config,rows))
 a,b=pair
 assert {k:v for k,v in a[0].items() if k not in ('case_id','requested_release_frame')}=={
  k:v for k,v in b[0].items() if k not in ('case_id','requested_release_frame')}
 assert a[0]['requested_release_frame']==360 and b[0]['requested_release_frame']==240
 keys=('emergency_center_xy_m','requested_emergency_authorized',
       'requested_flashing_lights','requested_officer_direction')
 assert all(all(a[1][i][k]==b[1][i][k] for k in keys) for i in range(600))
 assert all(a[1][i]['ego_center_xy_m']==b[1][i]['ego_center_xy_m'] and
            a[1][i]['ego_speed_mps']==b[1][i]['ego_speed_mps'] for i in range(240))
 assert a[1][240]['ego_speed_mps']==0 and b[1][240]['ego_speed_mps']>0
 assert a[1][360]['ego_speed_mps']>0
 report={'assignment_id':PREFIX,'comparison':'authored hold versus early release request',
  'construction_sha256':{suffix:case['construction_sha256'] for suffix,case in
   zip(('probe_a','probe_b'),manifest['cases'])},
  'road_sha256':sha(SOURCE/'emergency-road.xodr'),
  'frames_per_case':600,'duration_s':30,'source_camera_count':4,
  'same_road_emergency_trajectory_lamp_request_and_cameras':True,
  'only_control_difference':'ego release frame 360 versus 240',
  'original_native_observed':False,'qualifying_flashes_verified':False,
  'officer_direction_verified':False,'legal_verdict':None}
 (SOURCE/'request-comparison-proof.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
