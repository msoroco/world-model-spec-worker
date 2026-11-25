"""Build source-bound canonical stages for one-way travel selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
SOURCE = json.loads((HERE.parents[1] / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
LAW = SOURCE['law']
LAW_ID = LAW['id']
CELL = SOURCE['cell']
ACTOR = SOURCE['actor']
TEMPLATE_ID = f'{LAW_ID}@{ACTOR}'
OUT = HERE / 'proposals'


def save(name, value):
    path = OUT / f'{name}.json'
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': f'proposals/{name}.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
                       'relevance_type': 'specific_match', 'confidence': 'high',
                       'notes': 'The exact one-way highway cell and driver match the designated and signposted direction rule.'}],
    'borderline_excluded': []
}
batch_ref = save('relevance_batch', relevance)
relevance_ref = save('relevance', relevance)
template = {
    'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
    'status': 'draft', 'quote': LAW['text'],
    'structure': {
        'law_id': LAW_ID,
        'activation': {'condition': 'A vehicle is driven upon a highway designated and signposted for one-way traffic.', 'numeric_conditions': []},
        'obligation': {'description': 'Drive only in the direction designated for that one-way highway.', 'type': 'must', 'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'Assess direction continuously while the vehicle is driven upon the governed highway.', 'numeric_conditions': []},
        'judgment_calls_needed': []
    },
    'parameter_refs': [
        {'name': 'requested_travel_direction', 'kind': 'controller', 'range_or_domain': 'designated or opposite requested setting'},
        {'name': 'observed_designation_and_signposting', 'kind': 'subject_behavior', 'range_or_domain': 'source reviewed designated direction, official signposting and original trajectory or unknown'}
    ]
}
template_ref = save('template', template)
bindings = {
    'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
    'context_refs': [], 'fixed_parameters': [],
    'variable_parameters': [
        {'name': 'requested_travel_direction', 'kind': 'controller', 'range_or_domain': 'designated or opposite', 'used_by_laws': [LAW_ID]},
        {'name': 'observed_designation_and_signposting', 'kind': 'subject_behavior', 'range_or_domain': 'original evidence or unknown', 'used_by_laws': [LAW_ID]}
    ]
}
bindings_ref = save('bindings', bindings)
cases = json.loads((OUT / 'cases.json').read_text())
selected = [item for item in cases['cases'] if item['case_id'] in
            (f'{ASSIGNMENT}__designated', f'{ASSIGNMENT}__opposite')]
baseline = {
    'case_id': f'{ASSIGNMENT}__baseline', 'target_law_id': None,
    'target_type': 'baseline', 'cell_id': CELL['cell_id'], 'actor': ACTOR,
    'rationale': 'Shared one-way highway and driver context; unselected recording.',
    'variable_assignments': {
        'requested_travel_direction': {'kind': 'controller', 'value': None, 'unit': 'category'},
        'observed_designation_and_signposting': {'kind': 'subject_behavior', 'value': None, 'unit': 'structured'}
    },
    'recording_description': selected[0]['recording_description'], 'unresolved_judgment_calls': []
}
for item in selected:
    previous = item['variable_assignments']
    requested = previous.get('travel_direction_vs_sign', previous.get('requested_travel_direction'))['value']
    item['variable_assignments'] = {
        'requested_travel_direction': {'kind': 'controller', 'value': requested, 'unit': 'category'},
        'observed_designation_and_signposting': {'kind': 'subject_behavior', 'value': None, 'unit': 'structured'}
    }
    item['target_type'] = 'compliant_attempt' if requested == 'designated' else 'violating_attempt'
    item['rationale'] = ('Requested travel along the sourced designated direction'
                         if requested == 'designated' else
                         'Requested travel opposed to the sourced designated direction')
    item['paired_probe_id'] = f'{ASSIGNMENT}__comparison'
    item['deliberate_differences'] = ['requested_travel_direction']
    item['probe'] = {'primary_variable': 'requested_travel_direction',
                     'comparison_or_standard': 'same designated and signposted one-way road, direction setting differs',
                     'target_value_or_branch': requested}
    item['unresolved_judgment_calls'] = [
        'Official sign authority, physical signposting and legal conclusion need original sources']
cases['cases'] = [baseline] + selected
cases_ref = save('cases', cases)
save('semantic-index', {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
                        'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
                                   'template': template_ref, 'judgment_observables': [],
                                   'bindings': bindings_ref, 'cases': cases_ref}})
