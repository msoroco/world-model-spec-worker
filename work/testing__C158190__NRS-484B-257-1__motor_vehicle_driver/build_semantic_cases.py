"""Draft controlled C158190 cases with explicit unresolved sweep work."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals'
TEMPLATE = json.loads((PROPOSALS / 'template.json').read_text())
BINDINGS = json.loads((PROPOSALS / 'bindings.json').read_text())
MANIFEST = json.loads((ROOT / 'execution-manifest.json').read_text())
LAW = TEMPLATE['law_id']


def channel(name, unit, method, window='entire original capture'):
    return {'name': name, 'unit': unit, 'method': method,
            'time_window': window, 'reference_frame': 'original Native frame',
            'sampling_rate_hz': 20,
            'uncertainty': 'sampled source history; between-frame state and legal meaning remain unresolved'}


def main():
    original = json.loads((PROPOSALS / 'cases.json').read_text())
    by_id = {item['case_id']: item for item in original['cases']}
    phrase_names = [j['phrase'] for j in TEMPLATE['structure']['judgment_calls_needed']]
    cases = []
    first = MANIFEST['cases'][0]['case_id']
    shared = copy.deepcopy(by_id[first]['recording_description'])
    added_channels = [
        channel('ego_distance_to_junction_m', 'm',
                'original approach-history position joined to sight rays'),
        channel('through_vehicle_position', 'structured record',
                'original through-actor body-center position and explicit absent-actor state'),
        channel('through_vehicle_speed', 'structured record',
                'measured finite-difference through-actor body-center speed and explicit absent-actor state'),
        channel('ego_crossing_body', 'structured record',
                'original ego body vertices and sourced junction overlap history'),
    ]
    additions = {channel['name']: channel for channel in added_channels}
    shared['channels'] = [additions.get(channel['name'], channel)
                          for channel in shared['channels']]
    present = {channel['name'] for channel in shared['channels']}
    shared['channels'].extend(channel for channel in added_channels
                              if channel['name'] not in present)
    def assignments(through, view):
        values = {
            'sign_type': ('yield_sign', 'categorical'),
            'stopping_reference': ('nearest_view', 'categorical'),
            'through_vehicle_state': (through, 'categorical'),
            'commanded_approach_speed': (6.0, 'm/s'),
            'commanded_view_speed': (view, 'm/s'),
            'ego_speed': (None, 'm/s'),
            'through_highway_sight_clear': (None, 'count'),
            'ego_in_intersection': (None, 'boolean'),
        }
        return {name: {'kind': next(v['kind'] for v in BINDINGS['variable_parameters']
                                     if v['name'] == name), 'value': value, 'unit': unit}
                for name, (value, unit) in values.items()}
    cases.append({
        'case_id': ROOT.name + '__baseline_context', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Neutral authored junction and sign context; no separate selected recording or legal outcome.',
        'variable_assignments': assignments('approaching', 2.0),
        'recording_description': copy.deepcopy(shared),
        'unresolved_judgment_calls': [],
    })
    variants = {
        'through_approaches': ('approaching', 2.0, 'through_vehicle_state'),
        'through_entered': ('already_entered', 2.0, 'through_vehicle_state'),
        'clear': ('absent', 4.0, 'through_vehicle_state'),
        'no_slow': ('approaching', 6.0, 'commanded_view_speed'),
    }
    for entry in MANIFEST['cases']:
        ident = entry['case_id']
        suffix = ident.rsplit('__yield_nearest_view_', 1)[-1]
        through, view, primary = variants[suffix]
        item = copy.deepcopy(by_id[ident])
        item['variable_assignments'] = assignments(through, view)
        item['recording_description'] = copy.deepcopy(shared)
        item['paired_probe_id'] = 'c158190-selected-nearest-view'
        item['deliberate_differences'] = ['through_vehicle_state', 'commanded_view_speed']
        item['probe'] = {
            'primary_variable': primary,
            'comparison_or_standard': 'controlled physical contrast; no legal outcome label',
            'target_value_or_branch': through if primary == 'through_vehicle_state' else view,
        }
        item['unresolved_judgment_calls'] = phrase_names
        cases.append(item)
    missing_by_phrase = {
        'proper signs': [
            'Add a scalar world_setup sign-face angle or placement parameter with a sourced Native readback and independent original-pixel face check.',
            'Document an engineering-feasible angle range and spacing; the current categorical sign_type cannot form a scalar sweep axis.',
        ],
        'point nearest the intersection where the driver has a view of approaching traffic on the through highway': [
            'Bind measured ego_distance_to_junction_m as a canonical observable and add a controllable view-location world_setup axis.',
            'Verify the sampled ray scan against original cameras, then source a feasible view-location range and spacing without claiming human recognition.',
        ],
        'immediate hazard': [
            'Add a through-vehicle speed controller target and canonical measured through_vehicle_speed binding, with original through-body and time evidence.',
            'Source a feasible speed range and spacing while keeping the statute free of any numeric hazard cutoff.',
        ],
        'yield the right-of-way': [
            'Complete a fixed commanded_view_speed sweep with through_vehicle_state held approaching; the current 4 m/s case has an absent through actor.',
            'Construct and prove the missing same-traffic 4 m/s exact case, then document source-grounded range and spacing without legal labels.',
        ],
    }
    sweeps = [{
        'sweep_id': f'c158190-judgment-{index}', 'target_law_id': LAW,
        'judgment_refs': [{'phrase': judgment['phrase'], 'note': judgment['note']}],
        'status': 'incomplete',
        'rationale': 'The selected four cases do not constitute a fixed physical sweep for this unresolved judgment.',
        'missing_inputs': missing_by_phrase[judgment['phrase']],
    } for index, judgment in enumerate(TEMPLATE['structure']['judgment_calls_needed'], 1)]
    output = {'cell_id': BINDINGS['cell_id'], 'actor': BINDINGS['actor'],
              'status': 'draft', 'cases': cases, 'sweep_specs': sweeps,
              'sweeps_expanded': False}
    (PROPOSALS / 'cases.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'baseline_definitions': 1, 'selected_cases': len(cases)-1,
                      'unresolved_sweep_specs': len(sweeps)}))


if __name__ == '__main__':
    main()
