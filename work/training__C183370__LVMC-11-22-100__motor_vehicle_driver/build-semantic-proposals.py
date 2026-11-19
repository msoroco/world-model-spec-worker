"""Build value-free, source-hashed semantic drafts for the selected CPU case pair."""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate as validate_delivery

assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
manifest = json.loads((ROOT / 'draft-measured-candidate-manifest.json').read_text())
proposal = json.loads((ROOT / 'proposals/cases.json').read_text())
law = assignment['law']
actor = assignment['actor']
law_id = assignment['law_id']
template_id = law_id + '@' + actor
directory = ROOT / 'proposals'


def write(name, value):
    path = directory / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    'cell_id': assignment['cell_id'], 'actor': actor, 'status': 'draft',
    'relevant_laws': [{'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
                       'confidence': 'high', 'relevance_type': 'specific_match',
                       'notes': 'The flagger/paved-shoulder cell supports a warning-person probe; newly repaired pavement and an actual warning act require original evidence.'}],
    'borderline_excluded': [],
}
r_batch = write('relevance_batch.json', relevance)
r_cell = write('relevance.json', relevance)

judgments = [
    ('pavement newly laid or repaired', 'Surface condition and repair history require independent original review.',
     ['ego_pose', 'pavement_footprint_contact'], ['surveyed_repair_region']),
    ('a person or a sign warning persons against riding or driving over such pavement',
     'The warning-person branch is selected; a nearby person alone does not prove a warning act. Barrier, warning-sign and closure-sign routes remain unselected.',
     ['warning_person_state', 'ego_pose'], ['surveyed_repair_region']),
    ('employees actually engaged in the paving or repair of such pavement',
     'The employee exception requires original role and activity evidence; no exception is presumed.',
     ['ego_pose'], ['surveyed_repair_region']),
]
template = {
    'template_id': template_id, 'law_id': law_id, 'actor': actor, 'status': 'draft',
    'quote': law['text'], 'parameter_refs': [],
    'structure': {
        'activation': {'description': 'Riding or driving a horse or vehicle over or across newly laid or repaired pavement with a barrier, a warning person or sign, or a highway-closure sign.',
                       'source_clause': law['text'].split('. The provisions')[0] + '.'},
        'obligation': {'type': 'prohibition', 'description': 'Do not ride or drive over or across the protected pavement.',
                       'source_clause': 'No person shall ride or drive any horse or vehicle over or across any pavement newly laid or repaired'},
        'exceptions': [{'source_clause': 'The provisions of this Section shall not apply to the employees actually engaged in the paving or repair of such pavement.',
                        'description': 'Employee actually engaged in paving or repair of that pavement.'}],
        'timing': {'description': 'Observe warning and pavement state when the vehicle would cross the pavement.'},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _, _ in judgments],
    },
}
t_ref = write('template.json', template)

j_refs = []
for number, (phrase, note, streams, contexts) in enumerate(judgments):
    requirements = {
        'observables': [{'name': name, 'unit': 'structured', 'description': 'Source-joined original observation for ' + phrase + '.'} for name in streams],
        'context_inputs': [{'name': name, 'unit': 'structured', 'description': 'Source-surveyed setup; actual repair status and human activity remain unverified.'} for name in contexts],
        'sweep_dimensions': [], 'landmarks': [],
        'recording_needs': [{'name': name, 'unit': 'structured', 'description': 'Preserve original frame-joined evidence for ' + phrase + '.'} for name in streams],
        'limitations': [note, 'Synthetic diagnostic rows and pixels cannot establish this judgment.'],
    }
    j_refs.append(write(f'judgment_observables_{number}.json', {
        'template_id': template_id, 'phrase': phrase, 'note': note,
        'status': 'draft', 'observable_requirements': requirements}))

names = [('surveyed_pavement_and_warning_person', 'world_setup'),
         ('requested_pavement_crossing', 'controller'),
         ('actual_body_contact', 'subject_behavior'),
         ('warning_act', 'subject_behavior')]
binding = {'cell_id': assignment['cell_id'], 'actor': actor, 'status': 'draft',
           'established_contexts': [],
           'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
           'context_refs': [], 'fixed_parameters': [],
           'variable_parameters': [{'name': name, 'kind': kind, 'range_or_domain': 'original source observation or authored request',
                                    'used_by_laws': [law_id]} for name, kind in names]}
b_ref = write('bindings.json', binding)

cases = []
baseline = copy.deepcopy(proposal['cases'][0])
baseline.update(case_id=ROOT.name + '__baseline', target_law_id=None,
                target_type='baseline', rationale='Shared source-surveyed setup for the selected warning-person comparison.')
cases.append(baseline)
for case in proposal['cases']:
    item = copy.deepcopy(case)
    item.update(target_type='judgment_sweep', paired_probe_id=ROOT.name + '__warning_person_pair',
                deliberate_differences=['requested_pavement_crossing'],
                probe={'primary_variable': 'requested_pavement_crossing',
                       'comparison_or_standard': 'physical contact coverage; statute judgments unresolved',
                       'target_value_or_branch': {'requested_pavement_crossing': case['variable_assignments']['requested_pavement_crossing']['value']}},
                unresolved_judgment_calls=[phrase for phrase, _, _, _ in judgments])
    cases.append(item)
canonical = {'cell_id': assignment['cell_id'], 'actor': actor, 'status': 'draft',
             'cases': cases, 'sweeps_expanded': True,
             'sweep_specs': [{'sweep_id': ROOT.name + '__scope_pending', 'target_law_id': law_id,
                              'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note, _, _ in judgments],
                              'rationale': 'Physical warning-route and exception sweep awaits source-grounded construction.',
                              'status': 'incomplete',
                              'missing_inputs': ['Original warning act and pavement repair evidence',
                                                 'Barrier, warning-sign and closure-sign route constructions',
                                                 'Employee exception source evidence']}],
             'unselected_statutory_routes': ['barrier', 'warning sign', 'highway closure sign', 'paving/repair employee exception']}
c_ref = write('canonical-cases.json', canonical)
index = {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
         'stages': {'relevance_batch': r_batch, 'relevance': r_cell, 'template': t_ref,
                    'judgment_observables': j_refs, 'bindings': b_ref, 'cases': c_ref}}
write('semantic-index.json', index)
print(json.dumps(validate_delivery(ROOT, assignment, manifest), sort_keys=True))
