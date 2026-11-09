"""Route measured zone fallback eligibility without choosing a delivery case."""
import argparse
import json
from pathlib import Path
from saved import measure


def route(bundle,saved):
    m=measure(bundle,saved)
    overlap=m['moving_body_rectangle_overlap_frames']
    mismatch=(overlap==0 if m['requested_zone_route'] else overlap>0)
    return {'format':'c10374-zone-measured-routing-v1',
        'case_id':m['case_id'],'candidate_id':m['candidate_id'],
        'source_kind':m['source_kind'],
        'triggers':{
            'fallback1':{'eligible':mismatch,
                'moving_body_rectangle_overlap_frames':overlap,
                'reason':'observed moving body/rectangle relation differs from target'},
            'fallback2':{'eligible':m['reviewed_boundary_frames']<240 or
                         m['reviewed_visible_boundary_frames']<1,
                'reviewed_boundary_frames':m['reviewed_boundary_frames'],
                'reason':'incomplete reviewed safety-zone boundary visibility'},
            'fallback3':{'eligible':not m['original_native_observed'] or
                         m['authored_rectangle_is_designated_zone'] is False,
                'original_native_observed':m['original_native_observed'],
                'reason':'missing original Native or authoritative zone designation'}},
        'selected_fallback':None,'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved',type=Path,required=True);a=p.parse_args()
    print(json.dumps(route(a.bundle,a.saved)))
