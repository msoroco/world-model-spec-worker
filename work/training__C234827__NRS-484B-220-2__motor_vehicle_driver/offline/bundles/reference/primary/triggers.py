"""Route rotary fallback requests from saved measurements, without selecting one."""
import argparse
import json
from pathlib import Path

from measure_saved import measure


def route(folder,expected_hashes=None):
    metric=measure(folder,expected_hashes)
    triggered={
        'fallback1_slow_for_entry_visibility':metric['entry_visible_frames']<20,
        'fallback2_outer_lane_for_center_deviation':
            metric['maximum_lane_center_deviation_m']>.2,
        'fallback3_stop_for_unverified_island_or_control':
            not metric['physical_island_verified'] or not metric['traffic_control_verified']}
    return {'format':'c234827-measured-fallback-routing-v1',
        'case':metric['case'],'source_hashes':metric['source_hashes'],
        'measurements':{
            'entry_visible_frames':metric['entry_visible_frames'],
            'maximum_lane_center_deviation_m':metric['maximum_lane_center_deviation_m'],
            'physical_island_verified':metric['physical_island_verified'],
            'traffic_control_verified':metric['traffic_control_verified']},
        'thresholds':{'entry_visible_frames_min':20,
                      'maximum_lane_center_deviation_m':.2},
        'triggered':triggered,'selected_candidate':None,
        'legal_verdict':None,'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(route(args.folder),indent=2))
