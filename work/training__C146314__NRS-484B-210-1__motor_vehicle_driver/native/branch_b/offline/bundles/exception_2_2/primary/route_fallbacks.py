"""Record measured paragraph (b) fallback eligibility; never select."""
import argparse
import json
from pathlib import Path

from measure_saved import measure


def route(bundle,saved):
    result=measure(bundle,saved)
    return {'format':'c146314-paragraph-b-measured-routing-v1',
        'case_id':result['case_id'],'candidate_id':result['candidate_id'],
        'triggers':{
            'fallback1':{'eligible':result['full_body_right_pass_frames']<1,
                'measured_full_body_right_pass_frames':result['full_body_right_pass_frames']},
            'fallback2':{'eligible':result['human_reviewed_condition_frames']<240,
                'measured_reviewed_condition_frames':result['human_reviewed_condition_frames']},
            'fallback3':{'eligible':not result['original_native_observed'],
                'original_native_observed':result['original_native_observed']}},
        'selected_fallback':None,'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved',type=Path,required=True);a=p.parse_args()
    print(json.dumps(route(a.bundle,a.saved)))
