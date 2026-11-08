"""Measure C135709 raw-prepared saved observations without legal promotion."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def finite(x):return type(x) in (int,float) and math.isfinite(x)

def measure(bundle,saved):
    bundle,saved=Path(bundle),Path(saved)
    cfg=json.loads((bundle/'config.json').read_text())
    receipt=json.loads((saved/'preparation-receipt.json').read_text())
    readback=json.loads((saved/'stand-readback.json').read_text())
    request=rows(bundle/'requested-tracks.jsonl')
    observed=rows(saved/'native-observed.jsonl')
    camera=rows(saved/'camera-frames.jsonl')
    review=rows(saved/'stand-review.jsonl')
    hashes={name:sha(saved/name) for name in
        ('native-observed.jsonl','camera-frames.jsonl',
         'stand-review.jsonl','stand-readback.json')}
    kind=readback.get('source_kind')
    if (kind not in ('synthetic_cpu','original_native') or
        cfg['road_sha256']!=sha(bundle/'stand-road.xodr') or
        cfg['tracks_sha256']!=sha(bundle/'requested-tracks.jsonl') or
        receipt.get('saved_hashes')!=hashes or
        receipt.get('case_id')!=cfg['case_id'] or
        receipt.get('candidate_id')!=cfg['candidate_id'] or
        receipt.get('source_kind')!=kind or
        receipt.get('original_native_observed')!=(kind=='original_native') or
        receipt.get('delivery_ready') is not False or
        readback.get('road_sha256')!=cfg['road_sha256'] or
        readback.get('request_sha256')!=cfg['tracks_sha256'] or
        readback.get('review_sha256')!=sha(saved/'stand-review.jsonl') or
        readback.get('sign_text')!='TAXICAB STAND' or
        readback.get('stand_polygon_x_m')!=[50,75] or
        readback.get('stand_polygon_y_m')!=[-8.25,-3.5] or
        readback.get('review_provenance')!=
            ('human_frame_review' if kind=='original_native' else 'synthetic_cpu') or
        any(readback.get(k) is not False for k in
            ('official_designation_verified','sign_appropriateness_verified',
             'non_taxicab_actual_use_verified','passenger_loading_exception_verified',
             'actual_parking_observed')) or
        readback.get('legal_verdict') is not None or
        not (len(request)==len(observed)==len(camera)==len(review)==240)):
        raise ValueError('C135709 prepared provenance differs')
    first=observed[0].get('native_frame')
    if type(first) is not int:raise ValueError('C135709 Native frame absent')
    stationary=0;occupied=0;visible=0;prior=None;longest=0;run=0
    for i,(req,row,frame,review_row) in enumerate(zip(request,observed,camera,review)):
        if (req.get('frame')!=i or row.get('frame')!=i or frame.get('frame')!=i or
            review_row.get('frame')!=i or row.get('native_frame')!=first+i or
            frame.get('camera_frame')!=first+i or
            review_row.get('native_frame')!=first+i or
            row.get('time_s')!=(i+1)/20 or
            frame.get('time_s')!=row['time_s'] or
            review_row.get('time_s')!=row['time_s'] or
            row.get('source_kind')!=kind or frame.get('source_kind')!=kind or
            review_row.get('source_kind')!=kind or
            row.get('witness')!=req['witness'] or
            row.get('candidate_id')!=cfg['candidate_id'] or
            row.get('road_id')!=517 or row.get('lane_id') not in (-1,-2) or
            row.get('ego_actor_id')!=readback.get('ego_actor_id') or
            row.get('ego_blueprint')!='vehicle.tesla.model3' or
            row.get('actual_parking_observed') is not False or
            type(frame.get('stand_sign_visible')) is not bool or
            type(frame.get('stand_polygon_visible')) is not bool or
            review_row.get('review_provenance')!=readback['review_provenance'] or
            not finite(review_row.get('reviewed_ego_y_m')) or
            not all(finite(row.get(k)) for k in
                ('ego_x_m','ego_y_m','ego_heading_deg','ego_speed_mps')) or
            row['ego_speed_mps']<0):
            raise ValueError(f'C135709 prepared frame differs at {i}')
        x,y=row['ego_x_m'],row['ego_y_m']
        if kind=='synthetic_cpu' and (abs(x-req['ego_x_m'])>1e-5 or
            abs(y-req['ego_y_m'])>1e-5 or
            abs(row['ego_speed_mps']-req['ego_speed_mps'])>1e-5):
            raise ValueError('C135709 synthetic prepared request differs')
        if prior is not None and abs(20*math.hypot(x-prior[0],y-prior[1])-
                                     row['ego_speed_mps'])>.65:
            raise ValueError('C135709 observed displacement differs')
        prior=(x,y)
        body=row.get('ego_body_xy_m')
        if (not isinstance(body,list) or len(body)!=8 or any(
            not isinstance(p,list) or len(p)!=2 or not all(map(finite,p)) or
            math.hypot(p[0]-x,p[1]-y)>3 for p in body)):
            raise ValueError('C135709 prepared body differs')
        standing=row['ego_speed_mps']<=.1
        contained=all(50<=p[0]<=75 and -8.25<=p[1]<=-3.5 for p in body)
        stationary+=standing;occupied+=standing and contained
        run=run+1 if standing and contained else 0
        longest=max(longest,run)
        visible+=frame['stand_sign_visible'] and frame['stand_polygon_visible']
    return {'format':'c135709-prepared-saved-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':kind,'stationary_frames':stationary,
        'full_body_stand_occupied_frames':occupied,
        'longest_continuous_stand_occupancy_s':longest/20,
        'stand_and_sign_visible_frames':visible,
        'official_designation_verified':False,
        'sign_appropriateness_verified':False,
        'non_taxicab_actual_use_verified':False,
        'passenger_loading_exception_verified':False,
        'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved-dir',type=Path,required=True);a=p.parse_args()
    print(json.dumps(measure(a.bundle,a.saved_dir)))
