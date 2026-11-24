"""C111250 CPU construction preflight; physical acquisition is still pending."""
import argparse
import json
from facility import check as check_facility, body_overlap

CASES = ('outside_cycle_lane', 'within_cycle_lane')
RATE_HZ = 20
FRAMES = 600


def check(case, candidate):
    if case not in CASES or candidate != 'primary':
        raise ValueError('Unknown exact cycle-facility case/candidate')
    geometry = check_facility()
    if not geometry['centerline_preserved'] or geometry['main_road_cycle_lane_ids'] != [-2] * 3:
        raise ValueError('Cycle facility is not continuous through centerline intersection')
    x = 1.75 if case == 'outside_cycle_lane' else 4.5
    row = {'body_xy_m': [[x - .9, -1], [x + .9, -1], [x + .9, 1], [x - .9, 1]],
           'speed_mps': 4.0}
    measured = body_overlap(row)
    if (measured['cycle_intersection_body_overlap_m2'] > 0) != (case == 'within_cycle_lane'):
        raise ValueError('Requested case and source-body overlap disagree')
    return {'passed': True, 'case': case, 'candidate': candidate, 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'geometry': geometry, 'example_saved_body': measured,
            'native_imported': False, 'physical_or_legal_outcome_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    if not args.check:
        parser.error('Original Native acquisition is not implemented in this partial construction')
    try:
        config = json.load(open('config.json'))
    except FileNotFoundError:
        config = {}
    print(json.dumps(check(args.case or config.get('case_suffix'),
                           args.candidate or config.get('candidate_id')), sort_keys=True))


if __name__ == '__main__':
    main()
