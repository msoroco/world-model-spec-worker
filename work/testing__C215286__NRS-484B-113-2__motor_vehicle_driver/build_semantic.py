"""Build the exact C215286 canonical stage proposals from frozen inputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads(Path('inputs/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/assignment.json').read_text())
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
OUT = ROOT / 'proposals'
OUT.mkdir(exist_ok=True)
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
CELL = ASSIGNMENT['cell_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE = LAW_ID + '@' + ACTOR


def save(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'relevant_laws': [
    {'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
     'relevance_type': 'driver backing on or over crosswalk in fixed C215286 reverse task',
     'confidence': 'medium', 'notes': 'Crosswalk source and original reverse/body relation require Native review.'}],
    'borderline_excluded': []}
refs = {'relevance_batch': save('relevance_batch.json', relevance), 'relevance': save('relevance.json', relevance)}
judgments = [
    {'phrase': 'on or over a crosswalk', 'note': 'Original marked crossing geometry and vehicle extent during backing need source review; boundary contact has no assigned legal cutoff.'},
]
params = [
    {'name': 'reverse_path', 'kind': 'controller', 'range_or_domain': 'source selected body relation: disjoint, contact, or overlap'},
]
template = {'template_id': TEMPLATE, 'law_id': LAW_ID, 'actor': ACTOR, 'quote': LAW['text'],
    'structure': {'law_id': LAW_ID,
                  'activation': {'condition': 'Vehicle driver backing near a crosswalk.', 'numeric_conditions': []},
                  'obligation': {'description': 'Driver shall not back on or over a crosswalk.', 'type': 'must_not', 'numeric_conditions': []},
                  'exceptions': [],
                  'timing': {'description': 'During the original backing interval.', 'numeric_conditions': []},
                  'judgment_calls_needed': judgments},
    'parameter_refs': params}
refs['template'] = save('template.json', template)
obs = {'template_id': TEMPLATE, 'phrase': judgments[0]['phrase'], 'note': judgments[0]['note'], 'status': 'draft',
       'observable_requirements': {'observables': [
           {'name': 'body_crosswalk_relation', 'unit': 'structured', 'description': 'Original 20 Hz vehicle footprint, crosswalk polygon, velocity, heading and reverse gear.'}],
           'context_inputs': [{'name': 'marked_crosswalk_source', 'unit': 'metadata', 'description': 'Original map hash and marked crossing source.'}],
           'sweep_dimensions': [], 'landmarks': [],
           'recording_needs': [{'name': 'reverse_body_crosswalk', 'unit': 'structured', 'description': 'Time joined body and marked crossing geometry while backing.'}],
           'limitations': ['Physical polygon contact is an engineering probe; legal boundary application remains unresolved.']}}
refs['judgment_observables'] = [save('judgment-1.json', obs)]
binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
           'established_contexts': ['C215286 residence district, reverse maneuver, crosswalk control; original marked crossing still requires verification'],
           'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
           'context_refs': [], 'fixed_parameters': [],
           'variable_parameters': [{**p, 'used_by_laws': [LAW_ID]} for p in params]}
refs['bindings'] = save('bindings.json', binding)
cases = []
for item in PLAN['cases']:
    case_id = item['case_id']
    target = item['target_physical_relation']
    description = {'channels': [{'name': 'reverse_body_crosswalk', 'unit': 'structured',
                    'method': 'Native original frame body and marked-crossing polygon measurement',
                    'time_window': 'full reverse maneuver', 'reference_frame': 'Native world XY',
                    'uncertainty': 'Actual body relation requires independent physical review', 'sampling_rate_hz': 20}],
                   'context_inputs': [{'name': 'marked_crosswalk_source', 'unit': 'metadata',
                    'method': 'Native map SHA-256 and marked-crossing geometry'}],
                   'limitations': ['No legal verdict is inferred from physical relation.']}
    cases.append({'case_id': case_id, 'target_law_id': LAW_ID, 'target_type': 'judgment_sweep',
                  'rationale': 'Controlled backing relation probe; no legal contact threshold.',
                  'variable_assignments': {'reverse_path': {'kind': 'controller', 'value': target,
                  'note': 'Requested physical relation; original outcome unverified'}},
                  'recording_description': description,
                  'unresolved_judgment_calls': [judgments[0]['phrase']],
                  'paired_probe_id': 'reverse_crosswalk_relation',
                  'deliberate_differences': ['reverse_path'],
                  'probe': {'primary_variable': 'reverse_path',
                  'comparison_or_standard': 'reverse_crosswalk_relation', 'target_value_or_branch': target}})
    # The construction's recording description must match exactly.
    path = ROOT / 'cases' / case_id.split('__')[-1] / 'construction.json'
    construction = json.loads(path.read_text())
    construction['recording_description'] = description
    path.write_text(json.dumps(construction, indent=2) + '\n')
case_stage = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'cases': cases,
              'sweep_specs': [], 'sweeps_expanded': True}
refs['cases'] = save('cases.json', case_stage)
index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT['assignment_id'],
         'stages': refs, 'status': 'draft_source_bound_pending_native_review',
         'exception_inventory': {'status': 'no_exception_in_assigned_crosswalk_clause',
           'source': 'inputs/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/assignment.json'}}
save('semantic-index.json', index)
print('authored', len(cases), 'exact semantic cases')
