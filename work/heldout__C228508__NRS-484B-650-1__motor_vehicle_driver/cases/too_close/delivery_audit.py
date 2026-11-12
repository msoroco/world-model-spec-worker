"""Independent delivery audit for red-device and close-following review sources."""
import argparse
from hashlib import sha256
import json
from math import cos,sin,pi
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from delivery_audit import audit as audit_following

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def _body_headway(row):
    ego,lead=row['ego'],row['lead']
    angle=ego['yaw_deg']*pi/180;forward=(cos(angle),sin(angle));origin=ego['position_m']
    project=lambda p:(p[0]-origin[0])*forward[0]+(p[1]-origin[1])*forward[1]
    gap=min(project(v) for v in lead['body_corners_m'])-max(project(v) for v in ego['body_corners_m'])
    speed=ego['speed_mps']
    return gap/speed if speed>.1 else None

def audit(case,attempt,*,diagnostic_fixture=False):
    root=Path(attempt);base=audit_following(case,root,diagnostic_fixture=diagnostic_fixture)
    source=root/'device_lane_sources.jsonl'
    if not source.is_file():raise ValueError('Original signal source missing')
    rows=[json.loads(line) for line in source.read_text().splitlines() if line]
    maps=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines() if line]
    if len(rows)!=len(maps) or len(rows)<3:raise ValueError('Signal frame coverage differs')
    for row,mapping in zip(rows,maps):
        if (row['frame'],row['time_s'])!=(mapping['carla_frame'],mapping['time_s']):
            raise ValueError('Signal original frame join differs')
        if not row.get('traffic_light_actor_id') or not row.get('opendrive_id'):
            raise ValueError('Original signal identity missing')
    events=json.loads((root/'event_annotations.json').read_text())
    device=[e for e in events if e['category']=='device']
    following=[e for e in events if e['category']=='too_close']
    if len(device)!=1 or not following:raise ValueError('Device/following review candidates missing')
    if any(e['category']=='marked_lane' for e in events):raise ValueError('Unrequested marked-lane candidate present')
    signal_sha=digest(source);body_source=root/'following_sources.jsonl';body_sha=digest(body_source)
    for e in device:
        if e.get('source_ref')!=source.name or e.get('source_sha256')!=signal_sha:
            raise ValueError('Device candidate source citation differs')
        row=next((r for r in rows if r['frame']==e['frame']),None)
        prior=next((r for r in rows if r['frame']==e['frame']-1),None)
        if row is None or prior is None or not prior['ego_station_m']<row['stop_station_m']<=row['ego_station_m'] or not row['native_light_state'].endswith('Red'):
            raise ValueError('Red device crossing source absent')
    for e in following:
        if e.get('source_ref')!=body_source.name or e.get('source_sha256')!=body_sha:
            raise ValueError('Following candidate source citation differs')
    if not diagnostic_fixture:
        bodies=[json.loads(line) for line in body_source.read_text().splitlines() if line]
        for e in following:
            row=next((r for r in bodies if r['frame']==e['frame']),None)
            if row is None or _body_headway(row) is None or not 0<_body_headway(row)<1.5:
                raise ValueError('Native short-headway review geometry absent')
        review=json.loads((root/'independent-physical-review.json').read_text())
        item=review.get('visible',{}).get('governing_traffic_device',{})
        camera=item.get('camera')
        if (camera not in base['cameras'] or item.get('observed') is not True or
                item.get('camera_sha256')!=base['cameras'][camera]['video_sha256'] or
                type(item.get('video_frame')) is not int or not 0<=item['video_frame']<len(rows)):
            raise ValueError('Independent original device pixel review missing')
    base['device_source_sha256']=signal_sha;base['following_source_sha256']=body_sha
    base['too_close_auditor_sha256']=digest(__file__)
    base['checks']['device_source']=True;base['checks']['following_source']=True
    base['checks']['too_close_native_geometry']=not diagnostic_fixture
    return base

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--diagnostic-fixture',action='store_true');a=p.parse_args()
    print(json.dumps(audit(a.case,a.attempt,diagnostic_fixture=a.diagnostic_fixture),indent=2))
if __name__=='__main__':main()
