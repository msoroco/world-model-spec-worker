"""Independent source audit of two distinct signal crossing candidates."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from delivery_audit import audit as audit_following

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()

def audit(case,attempt,*,diagnostic_fixture=False):
    root=Path(attempt)
    base=audit_following(case,root,diagnostic_fixture=diagnostic_fixture)
    source=root/'device_lane_sources.jsonl'
    if not source.is_file():raise ValueError('Original signal source missing')
    rows=[json.loads(line) for line in source.read_text().splitlines() if line]
    maps=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines() if line]
    if len(rows)!=len(maps) or len(rows)<3:raise ValueError('Signal frame coverage differs')
    first_ids=None
    for row,mapping in zip(rows,maps):
        if (row['frame'],row['time_s'])!=(mapping['carla_frame'],mapping['time_s']):
            raise ValueError('Signal frame join differs')
        obs=row.get('signal_observations',[])
        ids=[x.get('traffic_light_actor_id') for x in obs]
        if len(ids)!=2 or len(set(ids))!=2 or any(not x.get('opendrive_id') for x in obs):
            raise ValueError('Two original governed signals required')
        if first_ids is not None and ids!=first_ids:raise ValueError('Signal identity changed')
        first_ids=ids
    source_sha=digest(source)
    events=json.loads((root/'event_annotations.json').read_text())
    devices=[e for e in events if e['category']=='device']
    if len(devices)!=2 or devices[0]['frame']==devices[1]['frame'] or len({e['occurrence_id'] for e in devices})!=2:
        raise ValueError('Two source-distinct device events required')
    for e in devices:
        if e.get('source_ref')!=source.name or e.get('source_sha256')!=source_sha:
            raise ValueError('Device event lacks original source citation')
        row=next((r for r in rows if r['frame']==e['frame']),None)
        previous=next((r for r in rows if r['frame']==e['frame']-1),None)
        if row is None or previous is None:raise ValueError('Device event frame absent')
        crossed=[x for x in row['signal_observations'] if
                 previous['ego_station_m']<x['stop_station_m']<=row['ego_station_m'] and
                 x['native_light_state'].endswith('Red')]
        if len(crossed)!=1 or str(crossed[0]['traffic_light_actor_id']) not in e['occurrence_id']:
            raise ValueError('Red device crossing source absent')
    if not diagnostic_fixture:
        review=json.loads((root/'independent-physical-review.json').read_text())
        for actor in first_ids:
            item=review.get('visible',{}).get('traffic_control_device_'+str(actor),{})
            camera=item.get('camera')
            if (camera not in base['cameras'] or item.get('observed') is not True or
                    item.get('camera_sha256')!=base['cameras'][camera]['video_sha256'] or
                    type(item.get('video_frame')) is not int or
                    not 0<=item['video_frame']<len(rows)):
                raise ValueError('Independent original pixel review missing: '+str(actor))
    base['repeated_device_source_sha256']=source_sha
    base['repeated_device_auditor_sha256']=digest(__file__)
    base['checks']['two_device_sources']=True
    base['checks']['two_device_pixels']=not diagnostic_fixture
    return base

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--diagnostic-fixture',action='store_true');a=p.parse_args()
    print(json.dumps(audit(a.case,a.attempt,diagnostic_fixture=a.diagnostic_fixture),indent=2))
if __name__=='__main__':main()
