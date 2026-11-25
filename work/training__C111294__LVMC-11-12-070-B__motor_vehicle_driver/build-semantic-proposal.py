"""Build the draft canonical stage chain from the frozen law and paired requests."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = next(p for p in PACKAGE.parents if (p / 'batch.json').is_file())
ASSIGNMENT = json.loads((ROOT / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
CELL_ID = ASSIGNMENT['cell_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
PROPOSALS = PACKAGE / 'proposals'
PROPOSALS.mkdir(exist_ok=True)


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


quote = LAW['text']
relevance = {
    'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
    'relevant_laws': [{
        'law_id': LAW_ID, 'quote': quote, 'applies_to': [ACTOR],
        'relevance_type': 'direct', 'confidence': 'high',
        'notes': 'Exact frozen intersection and other-vehicle cell; original priority-road designation and antecedent require source review.'
    }], 'borderline_excluded': []
}
relevance_ref = write('relevance.json', relevance)
batch_ref = write('relevance-batch.json', relevance)

parameters = [
    {'name': 'requested_through_response', 'kind': 'controller',
     'range_or_domain': ['yield_hold', 'continue_approach']},
    {'name': 'observed_through_yield', 'kind': 'subject_behavior',
     'range_or_domain': 'original vehicle body and speed history, initially unknown'},
    {'name': 'observed_entrant_prior_yield', 'kind': 'subject_behavior',
     'range_or_domain': 'original entrant stop and traffic history, initially unknown'},
    {'name': 'observed_entrant_entry', 'kind': 'subject_behavior',
     'range_or_domain': 'original entrant body path toward or across through highway, initially unknown'}
]
template = {
    'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
    'quote': quote, 'status': 'draft',
    'structure': {
        'law_id': LAW_ID,
        'activation': {'condition': 'entering driver has first yielded and is about to enter or cross the through highway while another driver approaches the intersection on that highway', 'numeric_conditions': []},
        'obligation': {'type': 'must', 'description': 'the approaching through-highway driver shall yield right-of-way to that entering vehicle', 'source_clause': 'shall yield right-of-way to the vehicle about to enter or cross the through highway', 'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'after the entrant has yielded, while it is about to enter or cross and the other driver approaches the intersection', 'numeric_conditions': []},
        'judgment_calls_needed': []
    },
    'parameter_refs': parameters
}
template_ref = write('template.json', template)
bindings = {
    'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
    'established_contexts': ['authored through and entrant crossing; original Native road status, first yielding and physical motion require independent review'],
    'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
    'context_refs': [], 'fixed_parameters': [
        {'name': 'authored_intersection', 'value': True,
         'rationale': 'The exact construction requests a crossing intersection; Native readback and legal designation remain to review'}
    ],
    'variable_parameters': [dict(item, used_by_laws=[LAW_ID]) for item in parameters]
}
bindings_ref = write('bindings.json', bindings)

description = json.loads((PACKAGE / 'draft-primary' / 'construction.json').read_text())['recording_description']
base = {
    'requested_through_response': {'kind': 'controller', 'value': 'yield_hold', 'unit': 'categorical'},
    'observed_through_yield': {'kind': 'subject_behavior', 'value': None, 'unit': 'original frames'},
    'observed_entrant_prior_yield': {'kind': 'subject_behavior', 'value': None, 'unit': 'original frames'},
    'observed_entrant_entry': {'kind': 'subject_behavior', 'value': None, 'unit': 'original frames'}
}
pair = PACKAGE.name + '__right_of_way_comparison'
cases = []
for suffix, target_type, response in (
    ('baseline', 'baseline', 'yield_hold'),
    ('probe_1', 'compliant_attempt', 'yield_hold'),
    ('probe_2', 'violating_attempt', 'continue_approach'),
):
    assignments = json.loads(json.dumps(base))
    assignments['requested_through_response']['value'] = response
    case = {
        'case_id': PACKAGE.name + '__' + suffix,
        'target_law_id': None if suffix == 'baseline' else LAW_ID,
        'target_type': target_type,
        'rationale': 'Requested controller contrast on the same entrant, road, cameras and clock; actual behavior and legal outcome require original source review.',
        'variable_assignments': assignments,
        'unresolved_judgment_calls': [],
        'recording_description': description
    }
    if suffix != 'baseline':
        case.update({
            'paired_probe_id': pair,
            'deliberate_differences': ['requested_through_response'],
            'probe': {'primary_variable': 'requested_through_response',
                      'comparison_or_standard': 'requested yield hold versus continued through-road approach under the same entrant history',
                      'target_value_or_branch': response}
        })
    cases.append(case)
cases_ref = write('cases.json', {'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
                                'cases': cases, 'sweep_specs': []})
index = {
    'format': 'worker-semantic-delivery', 'assignment_id': PACKAGE.name,
    'status': 'draft', 'original_native_observed': False,
    'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
               'template': template_ref, 'judgment_observables': [],
               'bindings': bindings_ref, 'cases': cases_ref}
}
write('semantic-index.json', index)
print(json.dumps({'stage_count': 5, 'selected_case_count': 2,
                  'semantic_index_sha256': hashlib.sha256((PROPOSALS / 'semantic-index.json').read_bytes()).hexdigest()}, sort_keys=True))
