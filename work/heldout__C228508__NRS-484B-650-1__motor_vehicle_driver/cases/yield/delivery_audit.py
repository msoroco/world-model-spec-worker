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
    for category in ('device',):
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
    cross=root/'yield_sources.jsonl'
    yield_rows=[json.loads(line) for line in cross.read_text().splitlines() if line]
    trace=[json.loads(line) for line in (root/'driving_trace.jsonl').read_text().splitlines() if line]
    if len(yield_rows)!=len(rows) or len(trace)!=len(rows):
        raise ValueError('Original yield source frame coverage differs')
    identity=(yield_rows[0]['ego_actor_id'],yield_rows[0]['cross_actor_id'],yield_rows[0]['junction_id'],yield_rows[0]['ego_signal_actor_id'],yield_rows[0]['cross_signal_actor_id'])
    if identity[0]==identity[1] or identity[3]==identity[4]:
        raise ValueError('Cross-highway actor or signal identity overlaps')
    for y,s,m,t in zip(yield_rows,rows,maps,trace):
        if ((y['frame'],y['time_s'])!=(s['frame'],s['time_s']) or
                (y['frame'],y['time_s'])!=(m['carla_frame'],m['time_s']) or
                (y['frame'],y['time_s'])!=(t['frame'],t['time_s']) or
                y['ego_xy_m']!=[t['x_m'],t['y_m']] or
                (y['ego_actor_id'],y['cross_actor_id'],y['junction_id'],y['ego_signal_actor_id'],y['cross_signal_actor_id'])!=identity or
                y['ego_road_id']==y['cross_road_id'] or
                y['ego_signal_actor_id']!=s['traffic_light_actor_id'] or
                not y['ego_signal_state'].endswith('Red') or
                not y['cross_signal_state'].endswith('Green')):
            raise ValueError('Cross-highway original source or signal state differs')
    candidate=by_category.get('yield')
    if not diagnostic_fixture:
        if candidate is None or candidate.get('source_ref')!=cross.name or candidate.get('source_sha256')!=digest(cross):
            raise ValueError('Yield candidate lacks original source citation')
        target=next((r for r in yield_rows if r['frame']==candidate['frame']),None)
        if target is None or not target['ego_in_junction'] or not target['cross_in_junction'] or not any(r['cross_in_junction'] and not r['ego_in_junction'] for r in yield_rows if r['frame']<target['frame']):
            raise ValueError('Cross traffic did not enter before ego')
        review=json.loads((root/'independent-physical-review.json').read_text())
        for subject in ('cross_traffic_vehicle','governing_signal'):
            item=review.get('visible',{}).get(subject,{})
            camera=item.get('camera')
            if (camera not in base['cameras'] or item.get('observed') is not True or
                    item.get('camera_sha256')!=base['cameras'][camera]['video_sha256'] or
                    type(item.get('video_frame')) is not int or
                    not 0<=item['video_frame']<len(rows)):
                raise ValueError('Independent original pixel review missing: '+subject)
    base['device_lane_source_sha256']=source_sha
    base['yield_source_sha256']=digest(cross)
    base['yield_auditor_sha256']=digest(__file__)
    base['checks']['device_source']=True
    base['checks']['yield_source']=True
    base['checks']['yield_pixels']=not diagnostic_fixture
    return base


def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--diagnostic-fixture',action='store_true');a=p.parse_args()
    print(json.dumps(audit(a.case,a.attempt,diagnostic_fixture=a.diagnostic_fixture),indent=2))

if __name__=='__main__':main()
