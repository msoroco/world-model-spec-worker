"""Build source-bound canonical proposals for the selected parking cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
SOURCE = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
LAW = SOURCE['law']
CELL = SOURCE['cell']
LAW_ID = LAW['id']
ACTOR = SOURCE['actor']
TEMPLATE_ID = f'{LAW_ID}@{ACTOR}'
OUT = ROOT / 'proposals'
OUT.mkdir(exist_ok=True)


def save(name, value):
    path = OUT / f'{name}.json'
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': f'proposals/{name}.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'relevant_laws': [{
        'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
        'relevance_type': 'specific_match', 'confidence': 'high',
        'notes': 'The frozen one-way-road parking cell and actor match this exact left-side standing or parking rule.'
    }], 'borderline_excluded': []
}
relevance_batch_ref = save('relevance_batch', relevance)
relevance_ref = save('relevance', relevance)
template = {
    'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
    'status': 'draft', 'quote': LAW['text'],
    'structure': {
        'law_id': LAW_ID,
        'activation': {'condition': 'A laned roadway is restricted to one direction and the person stands or parks a vehicle on its left-hand side.', 'numeric_conditions': []},
        'obligation': {'description': 'Do not stand or park a vehicle on the left-hand side of that one-way roadway in the absence of the source exception.', 'type': 'must_not', 'numeric_conditions': []},
        'exceptions': [{
            'trigger': 'Official traffic-control devices are erected permitting the standing or parking at the governed location.',
            'effect': 'The stated prohibition does not apply to the permitted standing or parking.',
            'replacement_obligation': 'No replacement obligation is stated in this section.',
            'source_clause': 'unless official traffic-control devices are erected permitting such standing or parking'
        }],
        'timing': {'description': 'Assess the original standing or parking interval.', 'numeric_conditions': []},
        'judgment_calls_needed': []
    },
    'parameter_refs': [
        {'name': 'requested_left_parking_permission_device', 'kind': 'controller', 'range_or_domain': 'requested present or absent; actual official status remains source-review dependent'},
        {'name': 'observed_official_governing_permission', 'kind': 'subject_behavior', 'range_or_domain': 'original evidence of official erection, governance, and permission or unknown'}
    ]
}
template_ref = save('template', template)
bindings = {
    'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'established_contexts': [],
    'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
    'context_refs': [], 'fixed_parameters': [],
    'variable_parameters': [
        {'name': 'requested_left_parking_permission_device', 'kind': 'controller', 'range_or_domain': 'requested present or absent', 'used_by_laws': [LAW_ID]},
        {'name': 'observed_official_governing_permission', 'kind': 'subject_behavior', 'range_or_domain': 'original evidence or unknown', 'used_by_laws': [LAW_ID]}
    ]
}
bindings_ref = save('bindings', bindings)
cases = json.loads((OUT / 'cases.json').read_text())
selected = cases['cases']
baseline = {
    'case_id': f'{ASSIGNMENT}__baseline', 'target_law_id': None,
    'target_type': 'baseline', 'cell_id': CELL['cell_id'], 'actor': ACTOR,
    'rationale': 'Shared one-way road and actor context; unselected recording.',
    'variable_assignments': {
        'requested_left_parking_permission_device': {'kind': 'controller', 'value': None, 'unit': 'boolean'},
        'observed_official_governing_permission': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'}
    },
    'recording_description': selected[0]['recording_description'],
    'unresolved_judgment_calls': []
}
for item in selected:
    requested = item['variable_assignments']['requested_left_parking_permission_device']['value']
    item['target_type'] = 'compliant_attempt' if requested else 'violating_attempt'
cases['cases'] = [baseline] + selected
cases_ref = save('cases', cases)
index = {
    'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
    'stages': {'relevance_batch': relevance_batch_ref, 'relevance': relevance_ref,
               'template': template_ref, 'judgment_observables': [],
               'bindings': bindings_ref, 'cases': cases_ref}
}
save('semantic-index', index)
