"""Measure exact synthetic stand occupancy, stationary time and body containment."""
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
    source=bundle/'requested-tracks.jsonl';saved=bundle/'saved'
    request=rows(source);observed=rows(saved/'native-observed.jsonl')
    camera=rows(saved/'camera-frames.jsonl')
    review=rows(saved/'stand-review.jsonl')
    readback=json.loads((saved/'stand-readback.json').read_text())
    if (cfg['road_sha256']!=sha(bundle/'stand-road.xodr') or
        cfg['tracks_sha256']!=sha(source) or
        readback.get('source_kind')!='synthetic_cpu' or
        readback.get('road_sha256')!=cfg['road_sha256'] or
        readback.get('request_sha256')!=cfg['tracks_sha256'] or
        readback.get('review_sha256')!=sha(saved/'stand-review.jsonl') or
        readback.get('stand_polygon_x_m')!=[50,75] or
        readback.get('stand_polygon_y_m')!=[-8.25,-3.5] or
        readback.get('sign_text')!='TAXICAB STAND' or
        any(readback.get(k) is not False for k in
            ('official_designation_verified','sign_appropriateness_verified',
             'non_taxicab_actual_use_verified','passenger_loading_exception_verified',
             'actual_parking_observed')) or
        readback.get('legal_verdict') is not None or
        not (len(request)==len(observed)==len(camera)==len(review)==240)):
        raise ValueError('C135709 saved provenance differs')
    stationary=0;occupied=0;visible=0;prior=(10,-1.75)
    for i,(req,row,frame,review_row) in enumerate(zip(request,observed,camera,review)):
        if (req.get('frame')!=i or row.get('frame')!=i or frame.get('frame')!=i or
            row.get('native_frame')!=1000+i or frame.get('camera_frame')!=1000+i or
            row.get('time_s')!=(i+1)/20 or frame.get('time_s')!=row['time_s'] or
            row.get('source_kind')!='synthetic_cpu' or
            frame.get('source_kind')!='synthetic_cpu' or
            row.get('witness')!=req.get('witness') or
            row.get('candidate_id')!=req.get('candidate_id') or
            row.get('road_id')!=517 or row.get('lane_id')!=req.get('lane_id') or
            row.get('phase')!=req.get('phase') or
            row.get('ego_actor_id')!=135709 or
            row.get('ego_blueprint')!='vehicle.tesla.model3' or
            row.get('actual_parking_observed') is not False or
            type(frame.get('stand_sign_visible')) is not bool or
            type(frame.get('stand_polygon_visible')) is not bool or
            review_row.get('frame')!=i or review_row.get('native_frame')!=1000+i or
            review_row.get('time_s')!=row['time_s'] or
            review_row.get('source_kind')!='synthetic_cpu' or
            review_row.get('review_provenance')!='synthetic_cpu' or
            not finite(review_row.get('reviewed_ego_y_m')) or
            any(not finite(row.get(k)) for k in
                ('ego_x_m','ego_y_m','ego_heading_deg','ego_speed_mps'))):
            raise ValueError(f'C135709 saved frame join differs at {i}')
        x,y=row['ego_x_m'],row['ego_y_m']
        if (abs(x-req['ego_x_m'])>1e-5 or abs(y-req['ego_y_m'])>1e-5 or
            abs(row['ego_speed_mps']-req['ego_speed_mps'])>1e-5 or
            row['ego_heading_deg']!=0 or
            abs(20*math.hypot(x-prior[0],y-prior[1])-row['ego_speed_mps'])>.001):
            raise ValueError('C135709 saved motion differs')
        prior=(x,y)
        body=row.get('ego_body_xy_m')
        expected=[[round(x+dx,6),round(y+dy,6)]
                  for dx,dy in ((2.3,.9),(2.3,-.9),(-2.3,.9),(-2.3,-.9))]
        if body!=expected:raise ValueError('C135709 saved body differs')
        if row['ego_speed_mps']<=.1:stationary+=1
        contained=all(50<=p[0]<=75 and -8.25<=p[1]<=-3.5 for p in body)
        if contained and row['ego_speed_mps']<=.1:occupied+=1
        if frame['stand_sign_visible'] and frame['stand_polygon_visible']:visible+=1
        if req['stand_polygon_occupied_requested']!=(contained and row['phase']=='parked'):
            raise ValueError('C135709 requested stand occupancy differs')
    return {'format':'c135709-synthetic-saved-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':'synthetic_cpu',
        'source_hashes':{name:sha(saved/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','stand-review.jsonl','stand-readback.json')},
        'stationary_frames':stationary,'full_body_stand_occupied_frames':occupied,
        'stand_and_sign_visible_frames':visible,
        'actual_parking_observed':False,'official_designation_verified':False,
        'sign_appropriateness_verified':False,'legal_verdict':None,
        'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path)
    print(json.dumps(measure(p.parse_args().bundle)))
