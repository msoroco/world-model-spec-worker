"""Build source-bound draft semantic proposals for the exact school crossing pair."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AID = 'training__C394563__LVMC-11-18-020__motor_vehicle_driver'
FOLDER = ROOT / 'work' / AID
SOURCE = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
LAW = SOURCE['law']
CELL = SOURCE['cell']
LAW_ID = SOURCE['law_id']
ACTOR = SOURCE['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
OUT = FOLDER / 'proposals'
OUT.mkdir(exist_ok=True)

def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name + '.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

quote = LAW['text']
relevance = {'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
             'relevant_laws': [{'law_id': LAW_ID, 'quote': quote, 'applies_to': [ACTOR],
                                'relevance_type': 'specific_match', 'confidence': 'high',
                                'notes': 'The frozen school-crossing cell matches vehicle entry at a signed crossing; original sign, authority and person intent require review.'}],
             'borderline_excluded': []}
r1 = write('relevance-batch', relevance)
r2 = write('relevance', relevance)
judgments = [
    {'phrase': 'School-Xing', 'note': 'Actual displayed text, sign authorization and governed crosswalk require original source and independent authority review.'},
    {'phrase': 'attempting to cross the street', 'note': 'Person intention is qualitative; original occupation and motion are evidence, not a verdict.'},
]
template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR, 'status': 'draft',
            'quote': quote, 'structure': {
                'activation': {'description': 'Original marked school crosswalk near a school, displayed School-Xing sign, and a person within the vehicle approach-side half attempting to cross.',
                               'source_clause': 'where there is displayed a sign with the words "School-Xing,"'},
                'obligation': {'type': 'must_not', 'description': 'Driver must not enter the signed crosswalk during the source-qualified person condition.',
                               'source_clause': 'it shall be unlawful for the operator of any vehicle to drive into a crosswalk'},
                'exceptions': [], 'timing': {'description': 'Join original vehicle front entry with same-frame person position; do not infer intent from timing alone.'},
                'judgment_calls_needed': judgments}, 'parameter_refs': []}
t = write('template', template)
jrefs = []
for n, j in enumerate(judgments, 1):
    name = 'person_crosswalk_sign'
    req = {'observables': [{'name': name, 'unit': 'source state', 'description': 'Original person and sign source joined to surveyed crosswalk.'}],
           'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
           'recording_needs': [{'name': name, 'unit': 'source state', 'description': 'Record original source and frame join for review.'}],
           'limitations': ['Synthetic source proves software wiring only; sign display, official authority and person intention need independent original source review.']}
    jrefs.append(write('judgment-' + str(n), {'template_id': TEMPLATE_ID, 'phrase': j['phrase'], 'note': j['note'], 'status': 'draft', 'observable_requirements': req}))
bindings = {'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft', 'established_contexts': [],
            'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}], 'context_refs': [],
            'fixed_parameters': [{'name': 'school_crossing_context', 'value': 'same signed marked 12 ft crossing and 100 ft advance context in both selected cases',
                                  'rationale': 'Frozen law geometry and authored construction; official source status reserved.'}],
            'variable_parameters': [{'name': 'ego_entry_frame', 'kind': 'controller',
                                     'range_or_domain': 'original-frame feedback setpoint before or after approach-side person occupation',
                                     'used_by_laws': [LAW_ID]}]}
b = write('bindings', bindings)
original_cases = json.loads((OUT / 'cases.json').read_text())['cases']
recording = original_cases[0]['recording_description']
base = {'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Shared reference with fixed school crossing geometry and source review.',
        'variable_assignments': {'ego_entry_frame': {'kind': 'controller', 'value': None}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments], 'recording_description': recording}
cases = [base]
for n, original in enumerate(original_cases):
    frame = 240 if n == 0 else 320
    case = dict(original)
    case.update(target_type='boundary_probe',
                rationale='Source-bound occupied-at-entry probe' if n == 0 else 'Source-bound cleared-at-entry probe',
                variable_assignments={'ego_entry_frame': {'kind': 'controller', 'value': frame}},
                unresolved_judgment_calls=[j['phrase'] for j in judgments],
                paired_probe_id=AID + '__school_crossing_pair',
                deliberate_differences=['ego_entry_frame'],
                probe={'primary_variable': 'ego_entry_frame',
                       'comparison_or_standard': 'person occupancy on vehicle approach side at original front-entry frame',
                       'target_value_or_branch': 'occupied' if n == 0 else 'cleared'})
    cases.append(case)
proposal = {'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
            'sweep_specs': [{'sweep_id': 'school-crossing-intent-review', 'target_law_id': LAW_ID,
                             'judgment_refs': judgments, 'status': 'incomplete',
                             'rationale': 'Actual displayed sign, authority and person intent require source review; no synthetic threshold resolves them.',
                             'missing_inputs': ['Independent original sign pixels, marking authority and person intent evidence.']}],
            'sweeps_expanded': True, 'cases': cases}
c = write('cases', proposal)
index = {'format': 'worker-semantic-delivery', 'assignment_id': AID,
         'stages': {'relevance_batch': r1, 'relevance': r2, 'template': t,
                    'judgment_observables': jrefs, 'bindings': b, 'cases': c}}
write('semantic-index', index)
plan_path = FOLDER / 'case-plan.json'
plan = json.loads(plan_path.read_text())
for item in plan['cases']:
    item['target_type'] = 'boundary_probe'
    item['kind'] = 'delivery'
    item['comparison_variable'] = 'same_side_person_occupancy_at_vehicle_entry'
for item in plan['comparisons']:
    item['deliberate_differences'] = ['ego_entry_frame']
    item['comparison_variable'] = 'same_side_person_occupancy_at_vehicle_entry'
    item['fixed_conditions'] = ['same source-law school crossing, surveyed yellow marking and School-Xing sign geometry',
                                'same person trajectory and identity; only controlled ego front-entry frame changes',
                                'same 600 original frames at 20 Hz and synchronized four-view camera plan']
plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
print('semantic proposals written')
