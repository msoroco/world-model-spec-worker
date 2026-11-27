"""Source-bound draft canonical stages for the six exact roadway rest cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_drafts import DESCRIPTION
from selected_plan import AID, CASES

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT/'proposals'
ASSIGNMENT = json.loads((ROOT.parents[1]/'inputs'/AID/'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID, CELL_ID, ACTOR = ASSIGNMENT['law_id'], ASSIGNMENT['cell_id'], ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID+'@'+ACTOR


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS/name
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    return path


def variable(name, kind, domain):
    return {'name': name, 'kind': kind, 'range_or_domain': domain}


VARIABLES = [
    variable('requested_yaw_offset_deg', 'controller', '0, 35 or 180 degrees relative to authored lawful flow'),
    variable('requested_activity', 'controller', 'parking or passenger-associated standing request'),
    variable('observed_edge_angle_deg', 'subject_behavior', 'saved unsigned original heading versus edge tangent'),
    variable('observed_lawful_heading_deg', 'subject_behavior', 'saved signed original heading versus lawful flow'),
    variable('roadway_edge', 'world_setup', 'one-way roadway with identified outside edge'),
]


def assignments(setting):
    return {'requested_yaw_offset_deg': {'kind': 'controller',
                'value': setting['requested_yaw_offset_deg'], 'unit': 'deg'},
            'requested_activity': {'kind': 'controller',
                'value': setting['activity'], 'unit': 'category'},
            'observed_edge_angle_deg': {'kind': 'subject_behavior',
                'value': None, 'unit': 'deg'},
            'observed_lawful_heading_deg': {'kind': 'subject_behavior',
                'value': None, 'unit': 'deg'},
            'roadway_edge': {'kind': 'world_setup',
                'value': True, 'unit': 'boolean'}}


def main():
    relevance = {'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW_ID,
            'quote': 'No person shall stand or park a vehicle in a roadway other than parallel with the edge of the roadway headed in the direction of lawful traffic movement.',
            'applies_to': [ACTOR], 'relevance_type': 'specific_match',
            'confidence': 'low',
            'notes': 'The frozen roadway-edge cell activates a standing/parking orientation question; actual activity and Chapter exceptions need original-source review.'}],
        'borderline_excluded': []}
    write('relevance_batch.json', relevance)
    write('relevance.json', relevance)
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID,
        'actor': ACTOR, 'status': 'draft', 'quote': LAW['text'],
        'structure': {'law_id': LAW_ID,
            'activation': {'condition': 'Responsible person stands or parks a vehicle in a roadway; actual activity and roadway must be source established',
                           'numeric_conditions': []},
            'obligation': {'type': 'must',
                'description': 'Resting vehicle is parallel with the identified roadway edge and headed in lawful traffic direction',
                'source_clause': 'parallel with the edge of the roadway headed in the direction of lawful traffic movement',
                'numeric_conditions': []},
            'exceptions': [{'source_clause': 'Except as otherwise provided in this Chapter',
                'description': 'Review applicable Chapter provisions and location-specific controls; no exception inferred from authored angle'}],
            'timing': {'description': 'Judge during actual standing or parking, not the entry maneuver; no numeric duration or angular cutoff supplied',
                       'numeric_conditions': []},
            'judgment_calls_needed': []},
        'parameter_refs': VARIABLES}
    write('template.json', template)
    binding = {'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [{'name': 'roadway_edge_candidate',
            'source': 'Frozen cell and authored map; Native roadway, lawful direction and exceptions require review'}],
        'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW_ID]) for item in VARIABLES]}
    write('bindings.json', binding)
    baseline_setting = CASES[next(iter(CASES))]
    baseline = {'case_id': AID+'__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Shared roadway edge and source context without legal verdict',
        'variable_assignments': assignments(baseline_setting),
        'unresolved_judgment_calls': ['Chapter exception and actual activity require independent review'],
        'recording_description': DESCRIPTION}
    cases = [baseline]
    for case, setting in CASES.items():
        lawful = setting['pose'] == 'parallel_lawful'
        probe_variable = 'observed_lawful_heading_deg' if setting['pose'] == 'parallel_against_traffic' else 'observed_edge_angle_deg'
        cases.append({'case_id': case, 'target_law_id': LAW_ID,
            'target_type': 'compliant_attempt' if lawful else 'violating_attempt',
            'rationale': 'Measure at-rest roadway edge angle and lawful-flow heading for '+setting['activity']+'; requested pose is not a legal result',
            'variable_assignments': assignments(setting),
            'unresolved_judgment_calls': ['Actual '+setting['activity']+' activity, roadway classification, location controls and Chapter exceptions need independent review'],
            'recording_description': DESCRIPTION,
            'paired_probe_id': TEMPLATE_ID+':roadside_rest_matrix',
            'deliberate_differences': ['requested_yaw_offset_deg', 'requested_activity'],
            'probe': {'primary_variable': probe_variable,
                'comparison_or_standard': 'LVMC 11.52.040(A) roadway edge orientation and lawful traffic heading',
                'target_value_or_branch': setting['pose']+'_'+setting['activity'],
                'test_value': setting['pose'], 'operator': 'categorical', 'unit': 'category'}})
    write('cases.json', {'cell_id': CELL_ID, 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [], 'cases': cases})
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID,
        'stages': {name: {'path': 'proposals/'+name+'.json',
                          'sha256': sha(PROPOSALS/(name+'.json'))}
                   for name in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}}
    index['stages']['judgment_observables'] = []
    write('semantic-index.json', index)
    print(json.dumps({'selected_cases': len(cases)-1,
                      'semantic_index_sha256': sha(PROPOSALS/'semantic-index.json')}, sort_keys=True))


if __name__ == '__main__':
    main()
