"""Source-bound measured routing diagnostics for three distinct requests."""
import argparse
import json
from pathlib import Path

from measure_saved import measure


def route(folder, expected_hashes=None):
    saved=measure(folder,expected_hashes)
    diagnostics={
        'fallback1_slow_sign_approach':saved['entry_visible_sign_frames']==0,
        'fallback2_outer_lane_traverse':saved['maximum_lane_center_deviation_m']>0.2,
        'fallback3_stop_before_entry':not saved['designation_authority_verified'],
    }
    return {'format':'c150916-measured-fallback-routing-v1',
            'case':saved['case'],'source_hashes':saved['source_hashes'],
            'entry_visible_sign_frames':saved['entry_visible_sign_frames'],
            'maximum_lane_center_deviation_m':saved['maximum_lane_center_deviation_m'],
            'designation_record_status':saved['designation_record_status'],
            'triggered':diagnostics,'selected_candidate':None,
            'authority_verified':False,'physical_sign_verified':False,
            'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(route(args.folder),indent=2))
