"""Independent device/lane original-source extension to C228508 delivery audit."""
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
    if not source.is_file():raise ValueError('Original signal/lane source missing')
    rows=[json.loads(line) for line in source.read_text().splitlines() if line]
    maps=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines() if line]
    if len(rows)!=len(maps) or len(rows)<3:
        raise ValueError('Original signal/lane frame coverage differs')
    for row,mapping in zip(rows,maps):
        if ((row['frame'],row['time_s'])!=(mapping['carla_frame'],mapping['time_s']) or
                not row.get('traffic_light_actor_id') or not row.get('opendrive_id') or
                row.get('marked_lane_width_m',0)<=0):
            raise ValueError('Original signal/lane identity or geometry missing')
    events=json.loads((root/'event_annotations.json').read_text());by_category={e['category']:e for e in events}
    source_sha=digest(source)
    for category in ('device','marked_lane'):
        item=by_category.get(category)
        if item is None or item.get('source_ref')!=source.name or item.get('source_sha256')!=source_sha:
            raise ValueError('Device/lane event lacks original source citation: '+category)
        row=next((r for r in rows if r['frame']==item['frame']),None)
        if row is None:raise ValueError('Device/lane event frame absent')
        if category=='device':
            previous=next((r for r in rows if r['frame']==item['frame']-1),None)
            if (previous is None or previous['ego_station_m']>=row['stop_station_m'] or
                    row['ego_station_m']<row['stop_station_m'] or
                    not row['native_light_state'].endswith('Red')):
                raise ValueError('Red device crossing source absent')
        elif (not 700<=row['ego_station_m']<900 or
              row['lateral_center_shift_m']<=row['marked_lane_width_m']/2):
            raise ValueError('Marked-lane body excursion source absent')
    if not diagnostic_fixture:
        review=json.loads((root/'independent-physical-review.json').read_text())
        for subject in ('traffic_control_device','marked_lane_boundary'):
            item=review.get('visible',{}).get(subject,{})
            camera=item.get('camera')
            if (camera not in base['cameras'] or item.get('observed') is not True or
                    item.get('camera_sha256')!=base['cameras'][camera]['video_sha256'] or
                    type(item.get('video_frame')) is not int or
                    not 0<=item['video_frame']<len(rows)):
                raise ValueError('Independent original pixel review missing: '+subject)
    base['device_lane_source_sha256']=source_sha
    base['device_lane_auditor_sha256']=digest(__file__)
    base['checks']['device_source']=True
    base['checks']['marked_lane_source']=True
    base['checks']['device_lane_pixels']=not diagnostic_fixture
    person_source=root/'person_sources.jsonl'
    if not person_source.is_file():raise ValueError('Original person source missing')
    people=[json.loads(line) for line in person_source.read_text().splitlines() if line]
    if len(people)!=len(rows):raise ValueError('Original person frame coverage differs')
    person_sha=digest(person_source);identities=set()
    from math import hypot
    for row,p in zip(rows,people):
        if (row['frame'],row['time_s'])!=(p['frame'],p['time_s']):
            raise ValueError('Original person frame join differs')
        identities.add(p['person_actor_id'])
        if abs(hypot(*(a-b for a,b in zip(p['ego_xy_m'],p['person_xy_m'])))-p['center_distance_m'])>1e-4:
            raise ValueError('Original person center distance differs')
    if len(identities)!=1:raise ValueError('Person actor identity changed')
    person_events=[x for x in events if x['category']=='hazard' and x.get('target_type')=='person']
    if len(person_events)!=1 or person_events[0].get('source_ref')!=person_source.name or person_events[0].get('source_sha256')!=person_sha:
        raise ValueError('Person hazard candidate lacks original source citation')
    candidate=next((p for p in people if p['frame']==person_events[0]['frame']),None)
    if candidate is None or candidate['center_distance_m']>=4 or not 150<=candidate['ego_station_m']<=300:
        raise ValueError('Person proximity candidate source absent')
    if not diagnostic_fixture:
        review=json.loads((root/'independent-physical-review.json').read_text())
        item=review.get('visible',{}).get('person_hazard_target',{})
        camera=item.get('camera')
        if (camera not in base['cameras'] or item.get('observed') is not True or
                item.get('camera_sha256')!=base['cameras'][camera]['video_sha256'] or
                type(item.get('video_frame')) is not int or
                not 0<=item['video_frame']<len(rows)):
            raise ValueError('Independent original person pixel review missing')
    base['person_source_sha256']=person_sha
    base['person_auditor_sha256']=digest(__file__)
    base['checks']['person_source']=True
    base['checks']['person_pixels']=not diagnostic_fixture
    return base


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--diagnostic-fixture',action='store_true');a=p.parse_args()
    print(json.dumps(audit(a.case,a.attempt,diagnostic_fixture=a.diagnostic_fixture),indent=2))

if __name__=='__main__':main()
