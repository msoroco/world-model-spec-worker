"""Independent comparison of business-turn signaling draft requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
 manifest=json.loads((BASE/'draft-native-manifest.json').read_text())
 assert manifest['assignment_id']==PREFIX and manifest['status']=='draft_not_selected'
 assert [c['case_id'] for c in manifest['cases']]==[PREFIX+'__probe_a',PREFIX+'__probe_b']
 roads=ET.fromstring((SOURCE/'business-turn-road.xodr').read_text()).findall('road')
 assert len(roads)==2 and [r.get('length') for r in roads]==['100','50']
 pair=[]
 for case in manifest['cases']:
  path=BASE/case['construction'];assert sha(path)==case['construction_sha256']
  construction=json.loads(path.read_text())
  files={f['path']:f['content'] for f in construction['files']}
  config=json.loads(files['config.json'])
  rows=[json.loads(s) for s in files['requested-track.jsonl'].splitlines()]
  assert len(rows)==600
  assert all(r['frame']==i and r['time_s']==(i+1)/20 for i,r in enumerate(rows))
  assert config['road_sha256']==sha(SOURCE/'business-turn-road.xodr')
  assert config['district']=='business' and len(config['cameras'])==4
  assert config['physical_completion'] is False and config['legal_verdict'] is None
  pair.append((config,rows))
 a,b=pair
 assert {k:v for k,v in a[0].items() if k not in ('case_id','requested_signal_onset_frame')}=={
  k:v for k,v in b[0].items() if k not in ('case_id','requested_signal_onset_frame')}
 assert a[0]['requested_signal_onset_frame']==260 and b[0]['requested_signal_onset_frame']==320
 assert all({k:v for k,v in a[1][i].items() if k!='right_signal_on'}==
            {k:v for k,v in b[1][i].items() if k!='right_signal_on'}
            for i in range(600))
 assert a[1][260]['right_signal_on'] is True and b[1][260]['right_signal_on'] is False
 assert a[1][400]['right_turn_begins'] is True and b[1][400]['right_turn_begins'] is True
 report={'assignment_id':PREFIX,'comparison':'authored 35 versus 20 meter continuous turn signal',
  'construction_sha256':{suffix:case['construction_sha256'] for suffix,case in
    zip(('probe_a','probe_b'),manifest['cases'])},
  'road_sha256':sha(SOURCE/'business-turn-road.xodr'),
  'frames_per_case':600,'duration_s':30,'source_camera_count':4,
  'same_route_turn_weather_speed_and_cameras':True,
  'only_control_difference':'right signal onset frame 260 versus 320',
  'original_native_observed':False,'business_district_verified':False,
  'legal_verdict':None}
 (SOURCE/'request-comparison-proof.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
