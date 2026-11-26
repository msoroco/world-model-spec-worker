"""Build the source-bound C146314(3) plain causal-rule stage chain."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
REPO = ROOT.parents[1]
AID = ROOT.name
assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
plan = json.loads((ROOT / 'case-plan.json').read_text())
law = assignment['law']
LAW = law['id']
ACTOR = assignment['actor']
CELL = assignment['cell_id']
TEMPLATE = LAW + '@' + ACTOR
recording = json.loads((ROOT / 'construction.json').read_text())['recording_description']


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def ref(path):
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
             'relevant_laws': [{'law_id': LAW, 'quote': law['text'], 'applies_to': [ACTOR],
                                'relevance_type': 'specific_match', 'confidence': 'high',
                                'notes': 'The frozen one-way right-pass cell stages the exact paved-portion rule; original necessity remains unverified.'}],
             'borderline_excluded': []}
write(OUT / 'relevance_batch.json', relevance)
write(OUT / 'relevance.json', relevance)
structure = {'activation': {'condition': 'driver overtakes and passes another vehicle upon the right',
                            'source_clause': 'overtake and pass another vehicle upon the right',
                            'numeric_conditions': []},
             'obligation': {'type': 'must_not',
                            'description': 'The right pass must not require driving off the paved portion of the highway.',
                            'source_clause': 'shall not overtake and pass another vehicle upon the right when such movement requires driving off the paved portion of the highway',
                            'numeric_conditions': []},
             'exceptions': [],
             'timing': {'description': 'Measure paved footprint and feasible paved corridor during the right-side overlap.',
                        'numeric_conditions': []},
             'judgment_calls_needed': []}
write(OUT / 'template.json', {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                               'status': 'draft', 'quote': law['text'],
                               'structure': structure, 'parameter_refs': []})
parameters = [
    ('fixed_road_and_actors', 'world_setup', 'same one-way paved lanes, shoulder, vehicle blueprints and longitudinal speed requests'),
    ('lead_lateral_plan_m', 'world_setup', 'two planned lead lateral placements in meters'),
    ('ego_lateral_route_target_m', 'controller', 'two planned ego route lateral targets in meters'),
    ('ego_lateral_m', 'subject_behavior', 'original measured Native ego lateral position in meters'),
    ('right_pass_paved_surface', 'subject_behavior', 'source-derived body/pass/clearance observation; original capture pending'),
]
write(OUT / 'bindings.json', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
      'established_contexts': [{'name': 'right_pass_layout', 'source': 'frozen one_way_multilane/overtake_right/other_vehicle cell'}],
      'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
      'context_refs': [], 'fixed_parameters': [],
      'variable_parameters': [{'name': n, 'kind': k, 'range_or_domain': d, 'used_by_laws': [LAW]}
                              for n, k, d in parameters]})


def assignments(suffix):
    is_a = suffix == 'probe_a'
    return {'fixed_road_and_actors': {'kind': 'world_setup', 'value': 'C146314 authored fixed road/actors/speed/cameras'},
            'lead_lateral_plan_m': {'kind': 'world_setup', 'value': -2.0 if is_a else -6.0, 'unit': 'm'},
            'ego_lateral_route_target_m': {'kind': 'controller', 'value': -6.0 if is_a else -8.7, 'unit': 'm'},
            'ego_lateral_m': {'kind': 'subject_behavior', 'value': None, 'unit': 'm'},
            'right_pass_paved_surface': {'kind': 'subject_behavior', 'value': None, 'unit': 'structured'}}


baseline = {'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
            'rationale': 'Shared right-pass planning baseline; no recording selected.',
            'variable_assignments': assignments('probe_a'),
            'recording_description': recording, 'unresolved_judgment_calls': []}
cases = [baseline]
for suffix, target in (('probe_a', 'compliant_attempt'), ('probe_b', 'violating_attempt')):
    cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
                  'target_type': target,
                  'rationale': 'Fixed road and longitudinal motion; lateral plan tests paved right-pass feasibility without a physical or legal claim.',
                  'variable_assignments': assignments(suffix),
                  'recording_description': recording,
                  'unresolved_judgment_calls': [],
                  'paired_probe_id': AID + '__paved_right_pass_pair',
                  'deliberate_differences': ['lead_lateral_plan_m', 'ego_lateral_route_target_m'],
                  'probe': {'primary_variable': 'ego_lateral_route_target_m',
                            'comparison_or_standard': 'original body/road clearance and off-paved concurrency, with necessity review',
                            'target_value_or_branch': suffix}})
canonical = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
             'sweep_specs': [], 'sweeps_expanded': True, 'cases': cases}
write(OUT / 'canonical-cases.json', canonical)
write(OUT / 'cases.json', canonical)
index = {'format': 'worker-semantic-delivery', 'assignment_id': AID,
         'stages': {'relevance_batch': ref(OUT / 'relevance_batch.json'),
                    'relevance': ref(OUT / 'relevance.json'),
                    'template': ref(OUT / 'template.json'),
                    'judgment_observables': [],
                    'bindings': ref(OUT / 'bindings.json'),
                    'cases': ref(OUT / 'canonical-cases.json')}}
write(OUT / 'semantic-index.json', index)
print(json.dumps({'case_ids': [c['case_id'] for c in cases], 'index_sha256': ref(OUT / 'semantic-index.json')['sha256']}))
