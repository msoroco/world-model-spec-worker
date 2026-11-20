"""Compare retained original diagnostic sources at the other-area 300-foot boundary."""
import argparse
import json
import math
from pathlib import Path

from comparison_audit import distance_and_start, load_sources, require


def audit(comparison_id, left, right):
    require(left['hashes']['road.xodr'] == right['hashes']['road.xodr'], 'Authored road map changed')
    require(left['route']['district_type'] == right['route']['district_type'] == 'other', 'Other-area district context changed')
    require(left['weather'] == right['weather'] and left['weather']['precipitation'] == 0, 'Fixed dry weather changed')
    require(left['route']['approach_road_id'] == right['route']['approach_road_id'], 'Approach road changed')
    require(left['route']['outgoing_road_id'] == right['route']['outgoing_road_id'], 'Right-turn connector changed')
    ld, ls = distance_and_start(left['drive'])
    rd, rs = distance_and_start(right['drive'])
    if comparison_id == 'other_area_threshold_below_at':
        require(left['hashes']['body_history.jsonl'] == right['hashes']['body_history.jsonl'], 'Fixed ego body motion changed')
        require(left['hashes']['route_context.json'] == right['hashes']['route_context.json'], 'Fixed route context changed')
        require(ld < 91.44 and math.isclose(rd, 91.44, abs_tol=1e-7), 'Below/at 300-foot distance contrast missing')
        require(ls > rs, 'Below/at 300-foot signal starts are not ordered')
    elif comparison_id == 'other_area_threshold_at_above':
        require(math.isclose(ld, 91.44, abs_tol=1e-7) and rd > 91.44, 'At/above 300-foot distance contrast missing')
        require(len(right['body']) == len(left['body']) + 1, 'Above approach does not add one source sample')
        for a, b in zip(left['body'], right['body'][1:]):
            same_vertices = all(math.isclose(x, y, abs_tol=1e-10)
                                for va, vb in zip(a['body_vertices_m'], b['body_vertices_m'])
                                for x, y in zip(va, vb))
            require(a['road_id'] == b['road_id'] and same_vertices,
                    'Approach body trajectory changed beyond one lead sample')
        require(right['route']['turn_onset_frame'] == left['route']['turn_onset_frame'] + 1,
                'Above approach turn-onset extension missing')
    else:
        raise ValueError('Unknown comparison: ' + comparison_id)
    return {'format': 'worker-turn-signal-source-comparison', 'comparison_id': comparison_id,
            'source_scope': 'saved synthetic diagnostic original sources',
            'left_source_hashes': left['hashes'], 'right_source_hashes': right['hashes'],
            'left_continuous_signal_distance_m': ld, 'right_continuous_signal_distance_m': rd,
            'boundary_m': 91.44, 'left_signal_start_frame': ls, 'right_signal_start_frame': rs,
            'software_comparison_passed': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison-id', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison_id, load_sources(args.left), load_sources(args.right)), indent=2))


if __name__ == '__main__':
    main()
