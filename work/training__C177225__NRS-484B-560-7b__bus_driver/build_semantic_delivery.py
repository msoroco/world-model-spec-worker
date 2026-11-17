"""Build draft, source-hashed semantic stage proposals for the bus/officer pair."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SOURCE = Path('inputs') / ASSIGNMENT / 'assignment.json'
assignment = json.loads(SOURCE.read_text())
law_id = assignment['law_id']
actor = assignment['actor']
cell_id = assignment['cell_id']
quote = assignment['law']['text']
template_id = f'{law_id}@{actor}'
proposals = ROOT / 'proposals'
proposals.mkdir(exist_ok=True)


def write(name, value):
    path = proposals / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': f'proposals/{name}', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'relevant_laws': [{
        'law_id': law_id, 'quote': quote, 'applies_to': [actor],
        'relevance_type': 'specific_match', 'confidence': 'medium',
        'notes': 'Frozen cell names a railroad crossing and police officer; original authority, direction and bus approach still require review.'
    }],
    'borderline_excluded': []
}
relevance_batch = write('relevance_batch.json', relevance)
relevance_single = write('relevance.json', relevance)

variables = [
    {'name': 'rail_crossing_context', 'kind': 'world_setup', 'range_or_domain': 'authored railroad crossing geometry; original Native verification pending', 'used_by_laws': [law_id]},
    {'name': 'officer_stop_direction', 'kind': 'world_setup', 'range_or_domain': 'authored officer stop direction to the bus before its approach; original Native verification pending', 'used_by_laws': [law_id]},
    {'name': 'bus_obeys_officer_direction', 'kind': 'controller', 'range_or_domain': 'true or false requested controller behavior; original motion remains unverified', 'used_by_laws': [law_id]},
]
template = {
    'template_id': template_id, 'law_id': law_id, 'actor': actor, 'status': 'draft',
    'quote': quote,
    'structure': {
        'activation': {'condition': 'driver of a vehicle at a railroad crossing is governed by an official traffic-control device or directions of a police officer', 'source_clause': 'To fail to obey an official traffic-control device or the directions of a police officer at a railroad crossing.'},
        'obligation': {'type': 'must_obey', 'description': 'obey the governing police officer direction at the railroad crossing', 'source_clause': 'the directions of a police officer at a railroad crossing.'},
        'exceptions': [],
        'timing': {'description': 'direction must precede the bus response at the crossing; capture the entire approach and response'},
        'judgment_calls_needed': []
    },
    'parameter_refs': [{k: v[k] for k in ('name', 'kind', 'range_or_domain')} for v in variables]
}
template_ref = write('template.json', template)
bindings = {
    'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'established_contexts': [{'name': 'officer_direction_branch', 'source': 'frozen assignment branch and case plan; original Native verification pending'}],
    'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
    'context_refs': [], 'fixed_parameters': [], 'variable_parameters': variables
}
bindings_ref = write('bindings.json', bindings)

original = json.loads((proposals / 'cases.json').read_text())
by_suffix = {case['case_id'].rsplit('__', 1)[-1]: case for case in original['cases']}
selected = []
for suffix, target, value in [('reference', 'compliant_attempt', True), ('contrast', 'violating_attempt', False)]:
    case = dict(by_suffix[suffix])
    case['target_type'] = target
    case['paired_probe_id'] = f'{ASSIGNMENT}__officer_stop_pair'
    case['deliberate_differences'] = ['bus_obeys_officer_direction']
    case['probe'] = {
        'primary_variable': 'bus_obeys_officer_direction',
        'comparison_or_standard': 'paired authored stop-direction response under fixed railroad crossing and officer context',
        'target_value_or_branch': value
    }
    case['variable_assignments'] = {
        'rail_crossing_context': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'authored railroad crossing with generic rail proxy'},
        'officer_stop_direction': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'officer directs bus to stop before crossing'},
        'bus_obeys_officer_direction': {'kind': 'controller', 'unit': 'bool', 'value': value}
    }
    selected.append(case)
base = dict(selected[0])
base['case_id'] = f'{ASSIGNMENT}__baseline'
base['target_type'] = 'baseline'
base['rationale'] = 'Shared setup reference; no additional selected delivery recording'
for key in ('paired_probe_id', 'deliberate_differences', 'probe'):
    base.pop(key, None)
cases = {
    'format': 'worker-case-proposals', 'cell_id': cell_id, 'actor': actor,
    'status': 'draft', 'cases': [base] + selected, 'sweep_specs': []
}
cases_ref = write('cases.json', cases)
index = {
    'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
    'stages': {
        'relevance_batch': relevance_batch, 'relevance': relevance_single,
        'template': template_ref, 'judgment_observables': [],
        'bindings': bindings_ref, 'cases': cases_ref
    }
}
write('semantic-index.json', index)
print(json.dumps({'semantic_index': 'proposals/semantic-index.json', 'selected_cases': [c['case_id'] for c in selected]}, indent=2))
