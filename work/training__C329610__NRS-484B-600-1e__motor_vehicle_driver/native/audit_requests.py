"""Independent road-source and speed comparison audit of C329610 requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from speed_turn import measure

BASE=Path(__file__).resolve().parents[1]
SOURCE=Path(__file__).resolve().parent
PREFIX=BASE.name
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def audit():
 road=SOURCE/'road.xodr'
 source=BASE.parent/'training__C329610__NRS-484B-413-2__motor_vehicle_driver'/'native-constructions/scene.xodr'
 current={r.get('id'):r for r in ET.parse(road).getroot().findall('road')}
 original={r.get('id'):r for r in ET.parse(source).getroot().findall('road')}
 if set(current)!=set(original):raise ValueError('Same-cell road IDs differ')
 for ident in current:
  if ident!='1' and ET.tostring(current[ident])!=ET.tostring(original[ident]):
   raise ValueError('Left-turn or intersecting road source changed')
 prior=original['1'].find('./planView/geometry')
 extended=current['1'].find('./planView/geometry')
 if (float(prior.get('x'))+float(prior.get('length'))
     !=float(extended.get('x'))+float(extended.get('length'))
     or float(extended.get('length'))!=423):
  raise ValueError('Approach endpoint changed or extension absent')
 proof={};routes=[]
 for suffix,mph in (('probe_a',75),('probe_b',85)):
  path=BASE/'draft-native'/suffix/'construction.json'
  c=json.loads(path.read_text());files={x['path']:x['content'] for x in c['files']}
  config=json.loads(files['config.json'])
  if (c['case_id']!=PREFIX+'__'+suffix or config['road_sha256']!=sha(road)
      or config['requested_speed_mph']!=mph or files['road.xodr']!=road.read_text()):
   raise ValueError('Exact case/source binding differs')
  rows=[json.loads(x) for x in files['requested-track.jsonl'].splitlines()]
  m=measure(rows,'authored_native_request')
  if (m['frames_greater_than_80_mph']>0)!=(mph>80):
   raise ValueError('Requested speed contrast differs')
  routes.append([r['road_id'] for r in rows])
  proof[suffix]={'construction_sha256':sha(path),'maximum_requested_speed_mph':m['maximum_speed_mph'],
                 'requested_frames_greater_than_80_mph':m['frames_greater_than_80_mph'],
                 'route_road_ids':m['route_road_ids']}
 if [1,13,4]!=proof['probe_a']['route_road_ids'] or [1,13,4]!=proof['probe_b']['route_road_ids']:
  raise ValueError('Both request routes must complete left turn')
 return {'format':'c329610-left-turn-speed-request-comparison-v1',
         'road_sha256':sha(road),'source_road_sha256':sha(source),'probes':proof,
         'fixed_conditions':['same-cell two-way intersection and left-turn arc',
                             'same 30-second window and four-camera profile',
                             'same vehicle role and route road IDs'],
         'deliberate_difference':'requested approach speed profile',
         'original_native_observed':False,'physical_completion':False,'legal_verdict':None}

if __name__=='__main__':print(json.dumps(audit(),indent=2))
