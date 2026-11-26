"""Separate the exact law's stop, stand, park and direction-source branches."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = ROOT.name + '__'


def main():
    path = ROOT / 'case-plan.json'
    plan = json.loads(path.read_text())
    if any(case['case_id'].endswith('__stop_1') for case in plan['cases']):
        raise ValueError('Exact-law expansion already applied')
    by_suffix = {case['case_id'].removeprefix(PREFIX): case for case in plan['cases']}
    witness = [by_suffix['witness_1'], by_suffix['witness_2']]
    for case in witness:
        case['source_branch'] = 'park on a crosswalk'
        case['physical_target'] = case['physical_target'].replace('parks', 'parks')
    additions = []
    for activity in ('stop', 'stand'):
        verb = 'stops' if activity == 'stop' else 'stands'
        for number in (1, 2):
            case = json.loads(json.dumps(witness[number - 1]))
            case['case_id'] = PREFIX + f'{activity}_{number}'
            case['source_branch'] = f'{activity} on a crosswalk'
            case['physical_target'] = f'driver {verb} ' + (
                'clear of crosswalk footprint' if number == 1 else
                'with footprint occupying crosswalk')
            case['comparison_variable'] = f'{activity}_crosswalk_occupancy'
            case['controller']['requested_behavior'] = case['physical_target']
            additions.append(case)
        plan['comparisons'].append({
            'comparison_id': PREFIX + f'{activity}_comparison',
            'case_ids': [PREFIX + f'{activity}_{n}' for n in (1, 2)],
            'deliberate_differences': [f'{activity}_crosswalk_occupancy'],
            'fixed_conditions': ['same frozen cell, actor, crosswalk geometry, cameras and observation window',
                                 'only requested footprint relation differs; actual relation remains unobserved'],
        })
    for number in (1, 2):
        police = by_suffix[f'exception_3_{number}']
        police['source_branch'] = 'in compliance with directions of a police officer'
        police['physical_target'] = police['physical_target'].replace(
            'in compliance with the directions of a police officer or an official traffic-control device',
            'in compliance with directions of a police officer')
        police['controller']['requested_behavior'] = police['physical_target']
        police['comparison_variable'] = 'police_direction_source'
        device = json.loads(json.dumps(police))
        device['case_id'] = PREFIX + f'exception_4_{number}'
        device['source_branch'] = 'in compliance with directions of an official traffic-control device'
        device['physical_target'] = device['physical_target'].replace(
            'directions of a police officer', 'directions of an official traffic-control device')
        device['controller']['requested_behavior'] = device['physical_target']
        device['comparison_variable'] = 'official_device_direction_source'
        additions.append(device)
    plan['cases'].extend(additions)
    for comparison in plan['comparisons']:
        if comparison['comparison_id'].endswith('__exception_3_comparison'):
            comparison['deliberate_differences'] = ['police_direction_source']
    plan['comparisons'].append({
        'comparison_id': PREFIX + 'exception_4_comparison',
        'case_ids': [PREFIX + f'exception_4_{n}' for n in (1, 2)],
        'deliberate_differences': ['official_device_direction_source'],
        'fixed_conditions': ['same frozen cell, actor, crosswalk geometry, cameras and observation window',
                             'only cited official-device direction source changes; applicability remains unverified'],
    })
    baseline = plan['requirement_dispositions'][0]
    baseline['branch'] = 'park on a crosswalk'
    baseline['case_ids'] = [PREFIX + f'witness_{n}' for n in (1, 2)]
    for activity in ('stop', 'stand'):
        plan['requirement_dispositions'].append({
            'requirement': plan['law_id'], 'source': plan['source_law']['source'],
            'branch': f'{activity} on a crosswalk', 'status': 'selected_required',
            'case_ids': [PREFIX + f'{activity}_{n}' for n in (1, 2)],
            'evidence_or_gap': 'Exact activity is a requested capture target; original Native activity and legal scope are unverified.',
        })
    police = plan['requirement_dispositions'][3]
    police['branch'] = 'in compliance with directions of a police officer'
    police['case_ids'] = [PREFIX + f'exception_3_{n}' for n in (1, 2)]
    plan['requirement_dispositions'].append({
        'requirement': plan['law_id'], 'source': plan['source_law']['source'],
        'branch': 'in compliance with directions of an official traffic-control device',
        'status': 'exception_pending',
        'case_ids': [PREFIX + f'exception_4_{n}' for n in (1, 2)],
        'evidence_or_gap': 'Cited device identity, direction, actor response and legal applicability remain unverified.',
    })
    plan['timing_requirements'].append({
        'kind': 'activity_split',
        'requirement': 'Source says stop, stand or park; no legal duration cutoff is invented by the CPU measurement.'})
    path.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'cases': len(plan['cases']),
                      'comparisons': len(plan['comparisons']),
                      'dispositions': len(plan['requirement_dispositions'])}))


if __name__ == '__main__':
    main()
