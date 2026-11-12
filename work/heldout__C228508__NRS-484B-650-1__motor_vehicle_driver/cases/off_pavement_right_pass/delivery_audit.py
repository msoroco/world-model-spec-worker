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
    pass_source=root/'right_pass_sources.jsonl'
    if not pass_source.is_file():raise ValueError('Original right-pass source missing')
    pass_rows=[json.loads(line) for line in pass_source.read_text().splitlines() if line]
    trace_rows=[json.loads(line) for line in (root/'driving_trace.jsonl').read_text().splitlines() if line]
    following_rows=[json.loads(line) for line in (root/'following_sources.jsonl').read_text().splitlines() if line]
    if len(pass_rows)!=len(rows):raise ValueError('Right-pass frame coverage differs')
    from math import hypot
    for row,p,t,f in zip(rows,pass_rows,trace_rows,following_rows):
        if (row['frame'],row['time_s'])!=(p['frame'],p['time_s']):
            raise ValueError('Right-pass frame join differs')
        if hypot(p['ego_xy_m'][0]-t['x_m'],p['ego_xy_m'][1]-t['y_m'])>1e-3:
            raise ValueError('Right-pass ego original pose differs')
        if hypot(*(x-y for x,y in zip(p['lead_xy_m'],f['lead']['position_m'][:2])))>1e-3:
            raise ValueError('Right-pass lead original pose differs')
        right=p['right_axis_xy']
        if abs(hypot(*right)-1)>1e-3:raise ValueError('Right-edge axis invalid')
        offset=sum((x-y)*axis for x,y,axis in zip(p['ego_xy_m'],p['road_edge_xy_m'],right))
        if abs(offset-p['right_of_driving_edge_m'])>1e-3:
            raise ValueError('Original right-edge offset differs')
    candidates=[x for x in events if x['category']=='off_pavement_right_pass']
    if len(candidates)>1:raise ValueError('Multiple unreviewed pass candidates')
    pass_sha=digest(pass_source)
    for event in candidates:
        if event.get('source_ref')!=pass_source.name or event.get('source_sha256')!=pass_sha:
            raise ValueError('Right-pass candidate lacks original source citation')
        selected=next((p for p in pass_rows if p['frame']==event['frame']),None)
        if selected is None or selected['right_of_driving_edge_m']<=.3 or selected['ego_station_m']-selected['lead_station_m']<=5:
            raise ValueError('Right-side pass geometry absent')
    if not diagnostic_fixture:
        if len(candidates)!=1:raise ValueError('Native right-pass candidate absent')
        review=json.loads((root/'independent-physical-review.json').read_text())
        for subject in ('unpaved_surface','right_side_overtake'):
            item=review.get('visible',{}).get(subject,{})
            camera=item.get('camera')
            if (camera not in base['cameras'] or item.get('observed') is not True or
                    item.get('camera_sha256')!=base['cameras'][camera]['video_sha256'] or
                    type(item.get('video_frame')) is not int or
                    not 0<=item['video_frame']<len(rows)):
                raise ValueError('Independent original pixel review missing: '+subject)
    base['right_pass_source_sha256']=pass_sha
    base['right_pass_auditor_sha256']=digest(__file__)
    base['checks']['right_pass_source']=True
    base['checks']['right_pass_pixels']=not diagnostic_fixture
    return base


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--diagnostic-fixture',action='store_true');a=p.parse_args()
    print(json.dumps(audit(a.case,a.attempt,diagnostic_fixture=a.diagnostic_fixture),indent=2))

if __name__=='__main__':main()
