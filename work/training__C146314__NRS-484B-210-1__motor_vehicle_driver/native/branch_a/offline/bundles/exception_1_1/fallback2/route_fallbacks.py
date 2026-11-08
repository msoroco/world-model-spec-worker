"""Record measured paragraph (a) fallback eligibility without selecting a route."""
import argparse
import json
from pathlib import Path

from measure_saved import measure

def route(bundle,saved):
    result=measure(bundle,saved)
    triggers={
        'fallback1':{'eligible':result['passing_right_geometry_frames']==0,
            'metric':'passing_right_geometry_frames',
            'value':result['passing_right_geometry_frames'],
            'condition':'zero full-body right-pass frames; retry slower approach'},
        'fallback2':{'eligible':result['signal_pixel_reviewed_frames']<240,
            'metric':'signal_pixel_reviewed_frames',
            'value':result['signal_pixel_reviewed_frames'],
            'condition':'fewer than 240 signal-reviewed frames; use elevated overview'},
        'fallback3':{'eligible':not result['original_native_observed'] or
            result['requested_signal_mismatch_frames']>0,
            'metric':'original_native_observed and requested_signal_mismatch_frames',
            'value':[result['original_native_observed'],
                     result['requested_signal_mismatch_frames']],
            'condition':'original light-state evidence absent or request/observation mismatch; stop before pass'}}
    return {'format':'c146314-paragraph-a-measured-fallbacks-v1',
        'case_id':result['case_id'],'candidate_id':result['candidate_id'],
        'source_kind':result['source_kind'],'triggers':triggers,
        'selected_fallback':None,'original_native_observed':False,
        'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved-dir',type=Path,required=True)
    a=p.parse_args();print(json.dumps(route(a.bundle,a.saved_dir),indent=2))
