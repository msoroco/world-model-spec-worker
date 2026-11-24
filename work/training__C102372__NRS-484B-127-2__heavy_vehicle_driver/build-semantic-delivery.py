"""Build the exact-law draft semantic chain for the seven selected cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
MANIFEST = json.loads((HERE / 'execution-manifest.json').read_text())
OUT = HERE / 'proposals'
OUT.mkdir(exist_ok=True)
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
PHRASE = 'whenever conditions permit'
NOTE = 'The source leaves whether physical traffic and road conditions permit the space to independent review.'


def write(name: str, value: dict) -> dict:
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'relevant_laws': [{
        'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
        'relevance_type': 'specific_match', 'confidence': 'high',
        'notes': 'The selected cell includes a heavy truck following another qualifying truck on the hill crest.'}],
    'borderline_excluded': []}
relevance_ref = write('relevance', relevance)
batch_ref = write('relevance_batch', relevance)

template = {
    'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
    'status': 'draft', 'quote': LAW['text'],
    'structure': {
        'activation': {
            'source_clause': 'The driver of any truck or combination of vehicles 80 inches or more in overall width, which is following a truck, or combination of vehicles 80 inches or more in overall width',
            'description': 'Two separate trucks or combinations each have overall width at least 80 inches; the subject follows the lead in the same direction.'},
        'obligation': {
            'source_clause': 'leave a space of 500 feet so that an overtaking vehicle may enter and occupy such space without danger',
            'description': 'Observe the continuous original body-to-body space against the source 500-foot boundary and preserve the overtaking-entry safety question for review.'},
        'exceptions': [
            {'source_clause': 'this shall not prevent a truck or combination of vehicles from overtaking and passing any vehicle or combination of vehicles',
             'description': 'Observe the actual passing interval and body/lane motion.'},
            {'source_clause': 'This subsection does not apply to any vehicle or combination of vehicles while moving on a highway on which there are two or more lanes available for traffic moving in the same direction.',
             'description': 'Count available same-direction lanes from the original highway source.'}],
        'timing': {'source_clause': 'which is following a truck',
                   'description': 'Observe the full original following interval and passing state.'},
        'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
    'parameter_refs': []}
template_ref = write('template', template)

needs = {
    'observables': [
        {'name': 'surface_gap_m', 'unit': 'm', 'description': 'Original truck body and road-arc separation for the full following interval.'},
        {'name': 'ego_body_pose', 'unit': 'structured', 'description': 'Original subject truck class, body width, lane and motion.'},
        {'name': 'lead_body_pose', 'unit': 'structured', 'description': 'Original lead truck class, body width, lane and motion.'}],
    'context_inputs': [{'name': 'conditions_permit', 'unit': 'structured',
                        'description': 'Original traffic, road and obstacle context requiring independent review.'}],
    'sweep_dimensions': [], 'landmarks': [],
    'recording_needs': [
        {'name': 'ego_body_pose', 'unit': 'structured', 'description': 'Original subject truck body and lane.'},
        {'name': 'lead_body_pose', 'unit': 'structured', 'description': 'Original lead truck body and lane.'},
        {'name': 'camera_frame_join', 'unit': 'structured', 'description': 'Original four-view frame join.'}],
    'limitations': [
        'A synthetic CPU fixture cannot settle whether physical conditions permit 500 feet.',
        'A measured space does not decide whether an overtaking vehicle may enter without danger.']}
judgment_ref = write('judgment_observables_0', {
    'template_id': TEMPLATE_ID, 'phrase': PHRASE, 'note': NOTE,
    'status': 'draft', 'observable_requirements': needs})

bindings = {
    'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'established_contexts': [],
    'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
    'context_refs': [],
    'fixed_parameters': [{'name': 'hill_crest_route', 'kind': 'world_setup',
                          'value': 'same authored hill-crest route', 'used_by_laws': [LAW_ID]}],
    'variable_parameters': [{'name': 'selected_branch_request', 'kind': 'controller',
                             'range_or_domain': 'following gap, same-direction lane, passing and lead-braking selected branches',
                             'used_by_laws': [LAW_ID]}]}
bindings_ref = write('bindings', bindings)

pair = {'probe_1': 'gap_pair', 'probe_2': 'gap_pair',
        'two_lane_exception': 'lane_exception',
        'passing_hold': 'passing_pair', 'passing_overtake': 'passing_pair',
        'conditions_steady': 'conditions_pair', 'conditions_lead_brake': 'conditions_pair'}
cases = []
baseline_description = json.loads((HERE / MANIFEST['cases'][0]['construction']).read_text())['recording_description']
cases.append({
    'case_id': HERE.name + '__baseline', 'target_law_id': None,
    'target_type': 'baseline', 'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
    'rationale': 'Common hill-crest context; not a selected physical delivery case.',
    'variable_assignments': {'selected_branch_request': {'kind': 'controller', 'value': None}},
    'recording_description': baseline_description,
    'unresolved_judgment_calls': [PHRASE]})
for entry in MANIFEST['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[1]
    description = json.loads((HERE / entry['construction']).read_text())['recording_description']
    cases.append({
        'case_id': entry['case_id'], 'target_law_id': LAW_ID,
        'target_type': 'judgment_sweep', 'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
        'rationale': 'Source-bound selected ' + suffix + ' observation; legal conditions remain open.',
        'variable_assignments': {'selected_branch_request': {'kind': 'controller', 'value': suffix}},
        'recording_description': description,
        'paired_probe_id': pair[suffix], 'deliberate_differences': ['selected_branch_request'],
        'probe': {'primary_variable': 'selected_branch_request',
                  'comparison_or_standard': 'exact NRS 484B.127(2) branch and original source review',
                  'target_value_or_branch': suffix},
        'unresolved_judgment_calls': [PHRASE]})
cases_ref = write('cases', {
    'format': 'worker-canonical-cases-v1', 'cell_id': ASSIGNMENT['cell_id'],
    'actor': ACTOR, 'law_id': LAW_ID, 'status': 'draft', 'cases': cases,
    'sweep_specs': [{'sweep_id': 'c102372-conditions-review', 'target_law_id': LAW_ID,
                     'status': 'incomplete', 'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                     'rationale': 'Original-source conditions require independent physical and legal review.',
                     'missing_inputs': ['Independent original traffic and road condition review',
                                        'Original four-view pixel and passing-entry safety review']}],
    'sweeps_expanded': True})
write('semantic-index', {
    'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
    'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
               'template': template_ref, 'judgment_observables': [judgment_ref],
               'bindings': bindings_ref, 'cases': cases_ref}})
print(json.dumps({'cases': len(cases) - 1, 'stage_count': 6}, sort_keys=True))
