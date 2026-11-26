"""Author draft canonical City-space stages without a legal verdict."""

import hashlib
import json
from pathlib import Path

from build_constructions import description
from city_space import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROPOSALS = ROOT / 'proposals'
LAW = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())['law']
TEMPLATE = LAW['id'] + '@vehicle_parker'


def put(name, obj):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / (name + '.json')
    path.write_text(json.dumps(obj, indent=2) + '\n')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    return {
        'city_vehicle_status': {'kind': 'world_setup', 'value': case.city_vehicle,
                                'note': 'reviewed vehicle authority, never livery'},
        'council_space_designation': {'kind': 'world_setup', 'value': case.designated,
                                      'note': 'separate reviewed Council source'},
        'official_posting_status': {'kind': 'world_setup', 'value': case.posted,
                                    'note': 'exact device instruction and authority'},
        'governed_space_occupancy': {'kind': 'world_setup', 'value': case.inside_space,
                                     'note': 'original complete parked footprint'},
    }


def build():
    relevance = {'cell_id': 'C229439', 'actor': 'vehicle_parker', 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
                                    'applies_to': ['vehicle_parker'],
                                    'relevance_type': 'direct City-space parking rule',
                                    'confidence': 'high',
                                    'notes': 'Assigned park maneuver and parking restriction device.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': put('relevance_batch', relevance),
            'relevance': put('relevance', relevance)}
    variables = [
        {'name': 'city_vehicle_status', 'kind': 'world_setup',
         'range_or_domain': 'source-reviewed City vehicle or other vehicle'},
        {'name': 'council_space_designation', 'kind': 'world_setup',
         'range_or_domain': 'Council-designated or not designated'},
        {'name': 'official_posting_status', 'kind': 'world_setup',
         'range_or_domain': 'duly posted or marked versus lacking official posting'},
        {'name': 'governed_space_occupancy', 'kind': 'world_setup',
         'range_or_domain': 'complete parked footprint in versus outside governed space'},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'],
                'actor': 'vehicle_parker', 'quote': LAW['text'],
                'structure': {
                    'law_id': LAW['id'],
                    'activation': {'condition': 'Council may designate a City street or facility parking space for City vehicles; actual designation and City jurisdiction are sourced.',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must_not',
                                   'description': LAW['text'],
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Actual parked interval and full footprint in original frames.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': []},
                'parameter_refs': variables}
    refs['template'] = put('template', template)
    refs['judgment_observables'] = []
    binding = {'cell_id': 'C229439', 'actor': 'vehicle_parker', 'status': 'draft',
               'established_contexts': ['City street or facility', 'park maneuver',
                                        'parking restriction device'],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**item, 'used_by_laws': [LAW['id']]}
                                       for item in variables]}
    refs['bindings'] = put('bindings', binding)
    desc = description()
    baseline = {'case_id': ASSIGNMENT + '__baseline',
                'target_law_id': None, 'target_type': 'baseline',
                'rationale': 'Common municipal space, parking movement and reviewed source reference.',
                'variable_assignments': assignments(CASES[0]),
                'recording_description': desc,
                'unresolved_judgment_calls': ['City-vehicle scope and NRS definition incorporation remain unresolved.']}
    cases = [baseline]
    vars_by_case = ('city_vehicle_status', 'city_vehicle_status',
                    'council_space_designation', 'official_posting_status',
                    'governed_space_occupancy')
    for index, case in enumerate(CASES):
        variable = vars_by_case[index]
        cases.append({'case_id': ASSIGNMENT + '__' + case.name,
                      'target_law_id': LAW['id'],
                      'target_type': 'violating_attempt' if index == 0 else 'compliant_attempt',
                      'rationale': 'Observe sourced City-space conditions and original parking footprint without assigning legal liability.',
                      'variable_assignments': assignments(case),
                      'recording_description': desc,
                      'unresolved_judgment_calls': [
                          'City-vehicle scope and NRS definition incorporation remain unresolved.'],
                      'paired_probe_id': ('vehicle_status' if index < 2 else variable),
                      'deliberate_differences': [variable],
                      'probe': {'primary_variable': variable,
                                'comparison_or_standard': 'LVMC 11.52.340 source-bound condition',
                                'target_value_or_branch': case.name}})
    proposal = {'cell_id': 'C229439', 'actor': 'vehicle_parker',
                'status': 'draft', 'cases': cases, 'sweep_specs': []}
    refs['cases'] = put('cases', proposal)
    put('semantic-index', {'format': 'worker-semantic-delivery',
                           'assignment_id': ASSIGNMENT, 'stages': refs})


if __name__ == '__main__':
    build()
