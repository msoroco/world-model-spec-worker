"""Build source-quoted, judgment-limited semantic proposals for the rail cases."""

import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
PROPOSALS = FOLDER / 'proposals'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    original = json.loads((FOLDER.parents[1] / 'inputs' / FOLDER.name / 'assignment.json').read_text())
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    law_id, cell_id, actor = (original[key] for key in ('law_id', 'cell_id', 'actor'))
    quote = original['law']['text']
    template_id = law_id + '@' + actor
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law_id, 'quote': quote,
            'applies_to': [actor], 'relevance_type': 'specific_match',
            'confidence': 'high',
            'notes': 'Selected curbside driver cell near a physical railroad rail; actual geometry requires original review.'}],
        'borderline_excluded': []}
    for name in ('relevance', 'relevance_batch'):
        write(PROPOSALS / (name + '.json'), relevance)
    parameters = [
        {'name': 'requested_rail_footprint_gap_m', 'kind': 'controller',
         'range_or_domain': 'engineering placement relative to surveyed rail, metres'},
        {'name': 'requested_activity', 'kind': 'controller',
         'range_or_domain': 'stop, stand or park request'},
        {'name': 'requested_exception_context', 'kind': 'controller',
         'range_or_domain': 'traffic, other law, police direction or official device request'},
        {'name': 'observed_rail_activity', 'kind': 'subject_behavior',
         'range_or_domain': 'original body footprint, speed, rest and departure or unknown'},
    ]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'status': 'draft', 'quote': quote,
        'structure': {'law_id': law_id,
            'activation': {'condition': 'A driver stops, stands or parks within 50 feet of the nearest physical rail of a railroad.',
                           'numeric_conditions': [{'value': 50, 'unit': 'ft', 'quantity': 'distance to nearest rail'}]},
            'obligation': {'type': 'must_not',
                'description': 'Do not stop, stand or park within the statutory rail distance unless a source exception applies.',
                'source_clause': 'shall not stop, stand or park a vehicle',
                'numeric_conditions': []},
            'exceptions': [
                {'trigger': 'Necessary to avoid conflict with other traffic',
                 'effect': 'The prohibition has an exception only when actual necessity is established from original traffic evidence.',
                 'replacement_obligation': 'Retain original vehicle conflict observations for independent review.',
                 'source_clause': 'except when necessary to avoid conflict with other traffic'},
                {'trigger': 'In compliance with law',
                 'effect': 'The prohibition has an exception when another applicable law actually requires or permits the activity.',
                 'replacement_obligation': 'Retain and independently review the cited law and original conduct.',
                 'source_clause': 'in compliance with law'},
                {'trigger': 'Directions of a police officer',
                 'effect': 'The prohibition has an exception when an actual police direction applies.',
                 'replacement_obligation': 'Retain original officer direction and response for review.',
                 'source_clause': 'the directions of a police officer'},
                {'trigger': 'Official traffic-control device',
                 'effect': 'The prohibition has an exception when an official device direction applies.',
                 'replacement_obligation': 'Retain original device identity, indication and response for review.',
                 'source_clause': 'official traffic-control device'}],
            'timing': {'description': 'Observe the complete requested stop, stand or park interval; the law gives no activity duration threshold.',
                       'numeric_conditions': []},
            'judgment_calls_needed': []},
        'parameter_refs': parameters}
    write(PROPOSALS / 'template.json', template)
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'established_contexts': [],
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(p, used_by_laws=[law_id]) for p in parameters]}
    write(PROPOSALS / 'bindings.json', bindings)
    existing = json.loads((PROPOSALS / 'cases.json').read_text())
    description = existing['cases'][0]['recording_description']
    baseline_values = {
        'requested_rail_footprint_gap_m': {'kind': 'controller', 'value': None, 'unit': 'm'},
        'requested_activity': {'kind': 'controller', 'value': None, 'unit': 'category'},
        'requested_exception_context': {'kind': 'controller', 'value': None, 'unit': 'category'},
        'observed_rail_activity': {'kind': 'subject_behavior', 'value': None, 'unit': 'structured'},
    }
    baseline = {'case_id': FOLDER.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'cell_id': cell_id, 'actor': actor,
        'rationale': 'Unselected common rail, road and driver context; no original observation or legal verdict.',
        'variable_assignments': baseline_values,
        'recording_description': description, 'unresolved_judgment_calls': []}
    selected = []
    for item in plan['cases']:
        case_id = item['case_id']
        suffix = case_id.removeprefix(FOLDER.name + '__')
        if suffix.startswith('selected_'):
            suffix = suffix.split('__')[-1]
        activity = ('stop' if suffix.startswith('stop') else
                    'stand' if suffix.startswith('stand') else 'park')
        exception = next((name for name in ('traffic_conflict', 'other_law',
                                           'police_direction', 'official_device')
                          if suffix.startswith(name)), None)
        near = True if exception else suffix.endswith(('a', '_1'))
        values = json.loads(json.dumps(baseline_values))
        values['requested_rail_footprint_gap_m']['value'] = 12.5 if near else 16.5
        values['requested_activity']['value'] = activity
        values['requested_exception_context']['value'] = ((exception + ('_requested' if suffix.endswith('_1') else '_control'))
                                                         if exception else 'none')
        variable = 'requested_exception_context' if exception else 'requested_rail_footprint_gap_m'
        target_type = ('violating_attempt' if near else 'compliant_attempt') if suffix.startswith('condition_') else 'boundary_probe'
        selected.append({'case_id': case_id, 'target_law_id': law_id,
            'target_type': target_type, 'cell_id': cell_id, 'actor': actor,
            'rationale': 'Requested ' + activity + ' and nearest-rail source measurement; original rail identity, pixels and exception applicability require independent review.',
            'variable_assignments': values, 'recording_description': description,
            'unresolved_judgment_calls': ['original physical rail identity and gap',
                'actual activity and exception applicability; no legal verdict'],
            'paired_probe_id': (exception or activity) + '_rail_comparison',
            'deliberate_differences': [variable],
            'probe': {'primary_variable': variable,
                      'comparison_or_standard': 'same fixed rail cell, driver, cameras and source law',
                      'target_value_or_branch': values[variable]['value']}})
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'sweep_specs': [], 'sweeps_expanded': True,
             'cases': [baseline] + selected}
    write(PROPOSALS / 'cases.json', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': FOLDER.name,
        'stages': {name: {'path': 'proposals/' + name + '.json',
                          'sha256': sha(PROPOSALS / (name + '.json'))}
                   for name in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}}
    index['stages']['judgment_observables'] = []
    write(PROPOSALS / 'semantic-index.json', index)


if __name__ == '__main__':
    build()
