"""Four unselected policies and source-measured fallback gates per signed case."""
import json
import math
from pathlib import Path

from geometry import native_route
from measure_u_turn import measure


CANDIDATES=('primary','fallback1','fallback2','fallback3')
CASES=('witness_1','witness_2')


def parameters(case_suffix,candidate_id):
    if case_suffix not in CASES or candidate_id not in CANDIDATES:
        raise ValueError('Unknown signed U-turn case or candidate')
    return {'case_suffix':case_suffix,'candidate_id':candidate_id,
            'native_route_xy_m':native_route(case_suffix),
            'target_speed_mps':3.5 if candidate_id=='fallback1' else 5.0,
            'lookahead_m':5.5 if candidate_id=='fallback2' else 4.0,
            'sign_camera_xyz_m':[-12,11,6] if candidate_id=='fallback3' else [-12,9,5],
            'four_camera_views_required':True,
            'law_id':'NRS-484B-403-2','cell_id':'C104538',
            'actor':'motor_vehicle_driver','duration_s':24,'rate_hz':20,
            'selected':False}


def evaluate_fallbacks(folder,case_suffix):
    if case_suffix not in CASES:raise ValueError('Unknown signed U-turn case')
    root=Path(folder)
    samples=root/'native_samples.jsonl';mapping=root/'video_frames.jsonl'
    review_path=root/'sign-review.json';video=root/'approach.mkv'
    measured=measure(samples,mapping,review_path,video)
    rows=[json.loads(line) for line in samples.read_text().splitlines() if line.strip()]
    route=native_route(case_suffix)
    def error(center):
        x,y=center
        return min(math.hypot(x-a,y-b) for a,b in route)
    pre=[row for row in rows if row['native_center_xy_m'][0]<=0]
    if not pre:raise ValueError('Approach source missing')
    maximum=max(error(row['native_center_xy_m']) for row in pre)
    review=json.loads(review_path.read_text())
    count=review.get('full_body_and_sign_visible_frames')
    total=review.get('approach_frames')
    if type(count)!=int or type(total)!=int or not 0<=count<=total or total<20:
        raise ValueError('Original pixel visibility review incomplete')
    visibility=count/total
    completed=(measured['u_turn_within_governed_region_observed'] if case_suffix=='witness_2'
               else rows[-1]['native_center_xy_m'][0]>=10 and
                    rows[-1]['native_lane_id']==review['governed_approach_lane_id'])
    return {'fallback1':maximum>.35,'fallback2':not completed,'fallback3':visibility<.95,
            'metrics':{'maximum_approach_route_error_m':maximum,
                       'requested_movement_completed':completed,
                       'sign_and_body_visible_fraction':visibility},
            'source_hashes':measured['source_hashes'],
            'scope':'source-bound saved diagnostic; physical labels require original review'}
