"""Measure source-bound synthetic right-exit phases and circulating lane bodies."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def finite(x):return type(x) in (int,float) and math.isfinite(x)

def measure(bundle):
    bundle=Path(bundle);cfg=json.loads((bundle/'config.json').read_text())
    saved=bundle/'saved';track=bundle/'requested-tracks.jsonl'
    readback=json.loads((saved/'lane-readback.json').read_text())
    observed=rows(saved/'native-observed.jsonl')
    camera=rows(saved/'camera-frames.jsonl');requests=rows(track)
    if (cfg['tracks_sha256']!=sha(track) or cfg['road_sha256']!=sha(bundle/'right-exit-road.xodr') or
        readback.get('source_kind')!='synthetic_cpu' or
        readback.get('road_sha256')!=cfg['road_sha256'] or
        readback.get('request_sha256')!=cfg['tracks_sha256'] or
        readback.get('right_lane_id')!=-2 or readback.get('other_lane_id')!=-1 or
        readback.get('physical_roundabout_verified') is not False or
        readback.get('lane_allocation_verified') is not False or
        readback.get('actual_right_exit_verified') is not False or
        len(requests)!=len(observed)!=240 or len(camera)!=240):
        raise ValueError('C132497 saved provenance differs')
    phase_counts={'entry':0,'circulation':0,'exit':0}
    body_frames=0;visible=0;maximum_deviation=0;previous=None
    for i,(request,row,frame) in enumerate(zip(requests,observed,camera)):
        if (request.get('frame')!=i or row.get('frame')!=i or frame.get('frame')!=i or
            row.get('native_frame')!=1000+i or frame.get('camera_frame')!=row['native_frame'] or
            row.get('time_s')!=(i+1)/20 or frame.get('time_s')!=row['time_s'] or
            row.get('source_kind')!='synthetic_cpu' or frame.get('source_kind')!='synthetic_cpu' or
            row.get('witness')!=request.get('witness') or
            row.get('candidate_id')!=request.get('candidate_id') or
            row.get('phase')!=request.get('phase') or row.get('road_id')!=request.get('road_id') or
            row.get('lane_id')!=cfg['requested_lane_id'] or
            row.get('actual_exit_observed') is not False or
            type(frame.get('right_lane_visible')) is not bool or
            any(not finite(row.get(key)) for key in
                ('ego_x_m','ego_y_m','ego_heading_deg','ego_speed_mps')) or
            row['ego_speed_mps']<0):
            raise ValueError(f'C132497 saved frame join differs at {i}')
        for key in ('ego_x_m','ego_y_m','ego_heading_deg','ego_speed_mps'):
            if abs(row[key]-request[key])>1e-5:raise ValueError('C132497 saved request trace differs')
        body=row.get('ego_body_xy_m')
        if not isinstance(body,list) or len(body)!=4 or any(
            not isinstance(p,list) or len(p)!=2 or not all(finite(v) for v in p)
            for p in body):raise ValueError('C132497 saved body absent')
        x,y=row['ego_x_m'],row['ego_y_m']
        if any(math.hypot(p[0]-x,p[1]-y)>1.3 for p in body):
            raise ValueError('C132497 saved body detached')
        if previous is not None and abs(math.hypot(x-previous[0],y-previous[1])*20-row['ego_speed_mps'])>.6:
            raise ValueError('C132497 saved speed differs')
        previous=(x,y);phase_counts[row['phase']]+=1
        if row['phase']=='circulation':
            radius=math.hypot(x-22,y+22)
            deviation=abs(radius-cfg['requested_arc_radius_m'])
            if deviation>.5:raise ValueError('C132497 saved circulating center differs')
            maximum_deviation=max(maximum_deviation,deviation)
            lower,upper=((15,18.5) if row['lane_id']==-2 else (18.5,22))
            if all(lower<=math.hypot(p[0]-22,p[1]+22)<=upper for p in body):body_frames+=1
        if frame['right_lane_visible']:visible+=1
    if not all(phase_counts.values()) or body_frames!=phase_counts['circulation']:
        raise ValueError('C132497 saved route or body coverage differs')
    if cfg['candidate_id']=='fallback3' and (any(row['ego_speed_mps']!=0 for row in observed[:40]) or
        observed[40]['ego_speed_mps']<=0):
        raise ValueError('C132497 saved dwell differs')
    return {'format':'c132497-synthetic-saved-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':'synthetic_cpu',
        'source_hashes':{name:sha(saved/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json')},
        'phase_frames':phase_counts,'full_body_circulation_lane_frames':body_frames,
        'right_lane_visible_frames':visible,
        'maximum_lane_center_deviation_m':round(maximum_deviation,6),
        'requested_right_turn_heading_change_deg':-90 if phase_counts['exit'] else None,
        'right_lane_used':cfg['requested_lane_id']==-2,
        'actual_right_exit_observed':False,'physical_roundabout_verified':False,
        'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path)
    print(json.dumps(measure(p.parse_args().bundle)))
