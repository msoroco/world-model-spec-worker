"""Route three distinct C131364 fallback requests from saved measurements."""
import argparse
import json
from pathlib import Path

from measure_saved import measure

def route(folder,expected_hashes=None):
    measured=measure(folder,expected_hashes)
    low_visibility=measured['entry_visible_frames']<20
    lane_deviation=measured['maximum_lane_center_deviation_m']>.2
    unverified=(not measured['roundabout_verified'] or
                not measured['actual_left_exit_observed'])
    return {'format':'c131364-measured-fallback-routing-v1',
            'witness':measured['witness'],'source_hashes':measured['source_hashes'],
            'measurements':{'entry_visible_frames':measured['entry_visible_frames'],
                            'maximum_lane_center_deviation_m':measured['maximum_lane_center_deviation_m'],
                            'actual_left_exit_observed':measured['actual_left_exit_observed'],
                            'roundabout_verified':measured['roundabout_verified']},
            'thresholds':{'entry_visible_frames_min':20,
                          'maximum_lane_center_deviation_m':.2},
            'triggered':{'fallback1_slow_for_visibility':low_visibility,
                         'fallback2_elevated_overview_for_lane_ambiguity':lane_deviation,
                         'fallback3_stop_for_unverified_exit_or_roundabout':unverified},
            'selected_candidate':None,'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(route(args.folder),indent=2))
