"""Synthetic below/at/above 500-foot nine-body-ray source protocol.

This tests the pinned sight decoder contract, not a realized Native horizon.
"""

import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from traffic_spec_adapter.visibility import sight_distance


PROBE_M = 152.4
POINTS = [[float(x), float(y), float(z)] for x, y, z in
          ((0, 0, 1), (-2, -1, 0), (-2, 1, 0), (2, -1, 0), (2, 1, 0),
           (-2, -1, 2), (-2, 1, 2), (2, -1, 2), (2, 1, 2))]


def source(clear_side_m):
    if clear_side_m not in (152.0, 152.4, 152.8):
        raise ValueError('Only predeclared 500-foot boundary points are allowed')
    approaches = []
    for lane_id in (-1, 1):
        approaches.append({'lane_id': lane_id, 'direction_sign': 1 if lane_id > 0 else -1,
            'any_sample_clear_at_probe': clear_side_m >= PROBE_M,
            'body_rays_at_probe': [{'sample_index': i, 'clear': clear_side_m >= PROBE_M}
                                   for i in range(9)],
            'any_body_sight_horizon': {'bound': 'first_sampled_occlusion',
                'distance_m': clear_side_m, 'bracket_m': [clear_side_m, clear_side_m]},
            'centre_sight_horizon': {'bound': 'first_sampled_occlusion',
                'distance_m': clear_side_m, 'bracket_m': [clear_side_m, clear_side_m]}})
    return {'method': 'synthetic_nine_body_ray_protocol',
            'distance_convention': 'incoming driving-lane waypoint arc length to actor projected station',
            'visibility_criterion': 'any_of_nine_body_samples',
            'probe_distance_m': PROBE_M, 'eye_height_m': 1.4,
            'scan_step_m': 10.0, 'horizon_tolerance_m': .25,
            'ego_body_samples_m': POINTS, 'required_lane_ids': [-1, 1],
            'approaches': approaches, 'diagnostic_fixture': True}


def audit():
    rows = []
    for label, distance in (('below', 152.0), ('at', 152.4), ('above', 152.8)):
        packet = source(distance)
        measured, reason = sight_distance(packet)
        if measured != distance:
            raise ValueError('Pinned decoder changed 500-foot '+label+' observation')
        rows.append({'side': label, 'clear_side_m': measured, 'reason': reason,
                     'source': packet})
    missing = source(152.4)
    missing['approaches'].pop()
    if sight_distance(missing)[0] is not None:
        raise ValueError('Missing incoming direction was accepted')
    centre_only = source(152.4)
    centre_only['ego_body_samples_m'] = centre_only['ego_body_samples_m'][:1]
    if sight_distance(centre_only)[0] is not None:
        raise ValueError('Centre-only body ray was accepted')
    route_limited = source(152.4)
    route_limited['approaches'][0]['any_body_sight_horizon'] = {
        'bound': 'route_limit', 'unknown': True, 'distance_m': 100.0}
    if sight_distance(route_limited)[0] is not None:
        raise ValueError('Route-limited horizon was accepted')
    return {'format': 'worker-500ft-sight-boundary-protocol',
            'statutory_reference': 'NRS 484B.407', 'probe_distance_m': PROBE_M,
            'observations': rows,
            'rejected': ['missing incoming direction', 'centre-only ray', 'route-limited horizon'],
            'fixture_only': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(), indent=2) + '\n')
    print('500 ft below/at/above and three negative source controls passed')
