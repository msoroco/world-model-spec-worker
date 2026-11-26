"""Independent source-bound CPU comparison for exact school-zone branches.

The caller supplies saved attempts keyed by exact case. This reports measured
differences and rejects changed fixed conditions, without a legal verdict.
"""
import argparse
import json
from pathlib import Path

from measure_school_zone import AID, measure

SPECS = {
    'speed_boundary': ((1, 2, 3), 'speed', None),
    'no_school_day': ((3, 4), 'school_session_day', (True, False)),
    'half_hour_window': ((3, 5), 'half_hour_window_exception', (False, True)),
    'beacon_flash': ((3, 6), 'beacon_flashing', (True, False)),
    'nonbeacon_sign': ((7, 8), 'nonbeacon_sign_in_effect', (True, False)),
}
FIXED = ('zone_designated', 'ego_is_motor_vehicle', 'road_id',
         'travel_direction_id', 'authorized_mph', 'zone_station_bounds_m',
         'road_axis_xy', 'condition_stable_30s', 'school_session_day',
         'half_hour_window_exception', 'beacon_operational', 'pupils_in_class',
         'beacon_flashing', 'nonbeacon_sign_in_effect')


def case_id(number):
    return AID+'__probe_'+f'{number:02d}'


def compare(name, attempts):
    if name not in SPECS:
        raise ValueError('Unknown exact comparison')
    numbers, variable, expected = SPECS[name]
    if set(attempts) != {case_id(number) for number in numbers}:
        raise ValueError('Comparison must provide exactly its planned cases')
    contexts, observations, targets = [], [], []
    for number in numbers:
        cid = case_id(number)
        root = Path(attempts[cid])
        context = json.loads((root/'school_zone_context.json').read_text())
        config = json.loads((root/'config.json').read_text())
        if config.get('case_id') != cid or config.get('law_id') != 'NRS-484B-363-1' or config.get('actor') != 'heavy_vehicle_driver':
            raise ValueError('Comparison case construction identity differs')
        observation = measure(root, expected_case=cid)
        contexts.append(context)
        observations.append(observation)
        targets.append(config.get('target_mph'))
    changed = {variable} if variable != 'speed' else set()
    for key in FIXED:
        if key not in changed and any(c[key] != contexts[0][key] for c in contexts[1:]):
            raise ValueError('Fixed school-zone comparison condition changed: '+key)
    if variable == 'speed':
        if targets != [14, 15, 17] or not all(o['reviewed_activation_complete'] for o in observations):
            raise ValueError('Speed comparison target or activation differs')
        speeds = [o['maximum_observed_mph_in_zone'] for o in observations]
        if not (speeds[0] < 15 and abs(speeds[1]-15) < 1e-9 and speeds[2] > 15):
            raise ValueError('Observed below/at/above speed comparison failed')
    else:
        if targets != [17, 17] or tuple(c[variable] for c in contexts) != expected:
            raise ValueError('Declared school-zone exception contrast not measured: '+variable)
        speeds = [o['maximum_observed_mph_in_zone'] for o in observations]
        if any(v <= 15 for v in speeds):
            raise ValueError('Exception comparison lacks observed above-15 traversal')
    return {'format': 'c262666-school-zone-comparison-cpu',
            'assignment_id': AID, 'comparison_id': AID+'__'+name,
            'case_ids': [case_id(number) for number in numbers],
            'fixed_conditions_checked': [key for key in FIXED if key not in changed],
            'deliberate_difference': variable,
            'observed_maximum_zone_mph': speeds,
            'source_hashes': {o['case_id']: o['sources'] for o in observations},
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True, choices=SPECS)
    parser.add_argument('--attempt', action='append', required=True,
                        help='exact-case-id=path; repeat for each comparison member')
    args = parser.parse_args()
    attempts = dict(item.split('=', 1) for item in args.attempt)
    print(json.dumps(compare(args.comparison, attempts), sort_keys=True))
