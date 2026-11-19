"""Independent source-bound four-point speed comparison."""
import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import HERE, audit as audit_delivery, require
from physical_speed_audit import read_rows

SUFFIXES = ('below_80_mph', 'inside_80_mph', 'at_80_mph', 'above_80_mph')
REQUESTS = {'below_80_mph': 75.0, 'inside_80_mph': 79.5,
            'at_80_mph': 80.0, 'above_80_mph': 85.0}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed_config(config):
    result = dict(config)
    for name in ('case_id', 'selected_case_id', 'supported_case_ids',
                 'case_suffix', 'case', 'requested_setting_mph'):
        result.pop(name, None)
    return result


def compare(attempts, processing, *, diagnostic=False):
    require(set(attempts) == set(SUFFIXES) and set(processing) == set(SUFFIXES),
            'Comparison needs four exact speed-boundary cases')
    reviewed = {}
    for suffix in SUFFIXES:
        case_id = HERE.name + '__' + suffix
        reviewed[suffix] = audit_delivery(case_id, 'primary', attempts[suffix],
                                          processing[suffix], diagnostic=diagnostic)
    configs = {key: read(Path(attempts[key]) / 'config.json') for key in SUFFIXES}
    requests = {key: configs[key]['requested_setting_mph'] for key in SUFFIXES}
    require(requests == REQUESTS, 'Speed controller requests differ from four-point grid')
    fixed = [fixed_config(configs[key]) for key in SUFFIXES]
    require(all(row == fixed[0] for row in fixed[1:]),
            'Speed comparison changed a fixed construction setting')
    roads = {key: sha(Path(attempts[key]) / 'road.xodr') for key in SUFFIXES}
    require(len(set(roads.values())) == 1, 'Speed comparison changed authored road')
    mappings = {key: sha(Path(attempts[key]) / 'video_frames.jsonl') for key in SUFFIXES}
    require(len(set(mappings.values())) == 1, 'Speed comparison changed frame-time map')
    samples = {key: read_rows(Path(attempts[key]) / 'native_samples.jsonl') for key in SUFFIXES}
    first = samples[SUFFIXES[0]]
    for index in range(480):
        reference = first[index]
        for key in SUFFIXES[1:]:
            row = samples[key][index]
            require(row.get('other_actor_id') == reference.get('other_actor_id') and
                    row.get('other_position_m') == reference.get('other_position_m') and
                    row.get('other_body_vertices_m') == reference.get('other_body_vertices_m') and
                    row.get('ego_actor_id') == reference.get('ego_actor_id') and
                    row.get('ego_blueprint') == reference.get('ego_blueprint') and
                    row.get('ego_control') == reference.get('ego_control') and
                    row.get('time_s') == reference.get('time_s'),
                    'Speed comparison changed fixed actor, traffic or time source')
    observed = {}
    for key in SUFFIXES:
        receipt = read(processing[key])
        result = read(receipt['result'])
        observed[key] = result['realized_observables']['peak_speed_mph']['value']
    if not diagnostic:
        require(all(reviewed[key]['passed'] for key in SUFFIXES),
                'Original speed delivery review incomplete')
        require(len(set(round(value, 3) for value in observed.values())) == 4,
                'Original speed comparison did not realize distinct measured speeds')
    return {'format': 'c111294-independent-speed-comparison-v1',
            'comparison_id': HERE.name + '__comparison_main',
            'case_ids': [HERE.name + '__' + key for key in SUFFIXES],
            'passed': not diagnostic, 'diagnostic_source_shape_passed': True,
            'requested_speed_mph': requests, 'observed_peak_mph': observed,
            'fixed_source_sha256': {'road.xodr': roads[SUFFIXES[0]],
                                    'video_frames.jsonl': mappings[SUFFIXES[0]]},
            'fixed_conditions_checked': ['construction except requested speed',
                                         'authored road', 'other vehicle body and route',
                                         'ego actor and control policy', 'source frame time'],
            'exact_80_legal_relation': 'unresolved_with_0.2_mph_interval',
            'original_physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior comparison audit output')
    attempts = {key: args.attempt_root / key / 'primary/compatibility'
                for key in SUFFIXES}
    processing = {key: args.attempt_root / key / 'primary/saved/v0001/processing.json'
                  for key in SUFFIXES}
    result = compare(attempts, processing, diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'passed': result['passed'], 'diagnostic': args.diagnostic}))


if __name__ == '__main__':
    main()
