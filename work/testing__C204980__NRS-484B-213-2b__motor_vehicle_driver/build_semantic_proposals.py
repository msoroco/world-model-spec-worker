"""Build draft canonical stages for the exact railroad crossing branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_constructions import description

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
AID = ROOT.name
LAW = 'NRS-484B-213-2b'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = f'{LAW}@{ACTOR}'
VARIABLES = ('requested_ego_side', 'requested_probe_station_ft', 'source_road_direction')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build(assignment, plan, quote):
    if (assignment['assignment_id'], assignment['law_id'], assignment['actor']) != (AID, LAW, ACTOR):
        raise ValueError('frozen railroad assignment identity differs')
    if plan['law_text'] != quote or len(plan['cases']) != 6 or len(plan['comparisons']) != 5:
        raise ValueError('exact railroad law or case/comparison inventory differs')
    parameters = [
        {'name': 'requested_ego_side', 'kind': 'controller',
         'range_or_domain': ['left', 'right']},
        {'name': 'requested_probe_station_ft', 'kind': 'controller',
         'range_or_domain': [-5, 99, 100, 101]},
        {'name': 'source_road_direction', 'kind': 'world_setup',
         'range_or_domain': ['two_way', 'one_way']},
    ]
    relevance = {'cell_id': assignment['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
            'relevance_type': 'left-side driving within 100 feet of or traversing a railroad grade crossing, with one-way exception',
            'confidence': 'medium',
            'notes': 'Actual highway, railroad and grade-crossing qualification need original source and physical review.'}],
        'borderline_excluded': []}
    judgments = [
        {'phrase': 'left side of the highway',
         'note': 'Use original body corners and reviewed centerline without an invented legal lateral cutoff.'},
        {'phrase': 'railroad grade crossing',
         'note': 'Require source-reviewed stationary rail carrier other than streetcar and actual highway crossing at grade.'},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {'law_id': LAW,
                    'activation': {'condition': 'A vehicle approaches within 100 feet of or traverses a railroad grade crossing on a highway.',
                                   'numeric_conditions': [{'variable': 'distance to crossing', 'operator': 'within',
                                                           'value': 100, 'unit': 'feet'}]},
                    'obligation': {'type': 'must_not',
                                   'description': 'Vehicle must not be driven to the left side of the highway during the stated condition.',
                                   'numeric_conditions': []},
                    'exceptions': [{'trigger': 'Reviewed one-way highway designation',
                                    'effect': 'Subsection 2 does not apply',
                                    'replacement_obligation': 'No subsection 2 left-side prohibition inferred',
                                    'source_clause': 'Subsection 2 does not apply upon a one-way highway.'}],
                    'timing': {'description': 'Join original body-side, crossing extent, highway direction and camera frames over approach and traversal.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': judgments},
                'parameter_refs': parameters}
    binding = {'cell_id': assignment['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['C204980 source-gated railroad grade crossing; actual qualification pending local review'],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{**p, 'used_by_laws': [LAW]} for p in parameters]}
    proposed = []
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(AID + '__')
        side = 'left' if case['left_side_requested'] else 'right'
        direction = 'one_way' if case['one_way_highway'] else 'two_way'
        values = dict(zip(VARIABLES, (side, case['target_leading_distance_ft'], direction)))
        assignments = {name: {'kind': ('world_setup' if name == 'source_road_direction' else 'controller'),
                              'value': value} for name, value in values.items()}
        proposed.append({'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'status': 'draft',
            'rationale': f'{suffix} isolates original body station, side or one-way context; no physical/legal outcome is asserted.',
            'variable_assignments': assignments,
            'recording_description': description(),
            'paired_probe_id': AID + '__railroad_grade_crossing',
            'deliberate_differences': list(VARIABLES),
            'probe': {'primary_variable': ('source_road_direction' if case['one_way_highway']
                    else 'requested_ego_side' if not case['left_side_requested']
                    else 'requested_probe_station_ft'),
                    'comparison_or_standard': '100-foot statutory distance retained; crossing/body references are engineering assumptions',
                    'target_value_or_branch': suffix},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments]})
        if suffix in ('left_101ft', 'left_100ft', 'left_99ft'):
            epsilon = {'value': 1, 'unit': 'feet',
                       'rationale': 'One-foot diagnostic spacing around statutory 100 feet; not a legal tolerance.'}
            proposed[-1]['epsilon_used'] = epsilon
            proposed[-1]['probe'].update({
                'threshold_ref': 'activation.numeric_conditions[0]',
                'operator': 'within', 'unit': 'feet',
                'test_value': case['target_leading_distance_ft'],
                'epsilon_used': epsilon})
    by_id = {case['case_id']: case['variable_assignments'] for case in proposed}
    comparisons = []
    for comp in plan['comparisons']:
        members = comp['case_ids']
        changed = [name for name in VARIABLES if by_id[members[0]][name] != by_id[members[1]][name]]
        if len(changed) != 1:
            raise ValueError('railroad comparison changes more than one declared variable: ' + comp['comparison_id'])
        comparisons.append({'comparison_id': comp['comparison_id'],
                            'case_ids': members, 'fixed_conditions': comp['fixed_conditions'],
                            'changed_variable': changed[0],
                            'deliberate_differences': comp['deliberate_differences']})
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Shared reviewed map, actor and crossing reference for five controlled comparisons.',
                'variable_assignments': proposed[0]['variable_assignments'],
                'recording_description': description(),
                'unresolved_judgment_calls': [j['phrase'] for j in judgments]}
    sweeps = [{'sweep_id': f'c204980-judgment-{index}', 'target_law_id': LAW,
               'judgment_refs': [item], 'status': 'incomplete',
               'rationale': 'Original reviewed railroad/centerline and physical observations are required for qualitative context coverage.',
               'missing_inputs': ['Original reviewed railroad grade-crossing qualification',
                                  'Original body/camera visibility and highway source review']}
              for index, item in enumerate(judgments, 1)]
    cases_stage = {'cell_id': assignment['cell_id'], 'actor': ACTOR, 'status': 'draft',
                   'cases': [baseline, *proposed], 'comparisons': comparisons,
                   'sweep_specs': sweeps, 'sweeps_expanded': True}
    observable = []
    for judgment in judgments:
        names = ('rail_qualification', 'highway_direction', 'crossing_extent',
                 'ego_body_side_and_station', 'original_frame_and_camera_join')
        channels = [{'name': name, 'unit': 'structured record',
                     'description': 'Source-hashed original Native rail record'} for name in names]
        observable.append({'template_id': TEMPLATE, 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {'observables': channels, 'context_inputs': [],
                'sweep_dimensions': [{'name': 'source_reviewed_crossing_body_position',
                                      'unit': 'categorical',
                                      'description': 'Original body/crossing relation, without invented legal cutoff'}],
                'landmarks': [], 'recording_needs': channels,
                'limitations': ['Synthetic fixtures cannot establish original railroad qualification, camera visibility or legal judgment.']}})
    return {'relevance_batch': relevance, 'relevance': relevance,
            'template': template, 'judgment_observables': observable,
            'bindings': binding, 'cases': cases_stage}


def main():
    assignment_path = PROJECT / 'inputs' / AID / 'assignment.json'
    plan_path = ROOT / 'case-plan.json'
    coverage_path = PROJECT / 'inputs/coverage/branch-sources.json'
    quote = json.loads(coverage_path.read_text())['laws'][LAW]['law']['text']
    stages = build(json.loads(assignment_path.read_text()),
                   json.loads(plan_path.read_text()), quote)
    destination = ROOT / 'proposals'
    refs = {}
    for name, payload in stages.items():
        if name == 'judgment_observables':
            refs[name] = []
            for index, item in enumerate(payload, 1):
                path = destination / f'judgment-{index}.json'
                write(path, item)
                refs[name].append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        else:
            path = destination / f'{name}.json'
            write(path, payload)
            refs[name] = {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID,
             'status': 'draft', 'physical_acceptance': 'unverified',
             'source': {'path': str(assignment_path.relative_to(PROJECT)),
                        'sha256': sha(assignment_path)},
             'sources': [{'path': str(path.relative_to(PROJECT)), 'sha256': sha(path)}
                         for path in (assignment_path, plan_path, coverage_path)],
             'stages': refs}
    write(destination / 'semantic-index.json', index)
    print('six exact railroad semantic cases and five isolated comparisons bound')


if __name__ == '__main__':
    main()
