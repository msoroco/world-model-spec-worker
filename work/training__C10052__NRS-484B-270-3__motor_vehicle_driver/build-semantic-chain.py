"""Build draft semantic stages for the exact C10052 selected delivery cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals'
ASSIGNMENT = json.loads((ROOT.parents[1] / 'inputs' / ROOT.name / 'assignment.json').read_text())
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
CELL_ID = ASSIGNMENT['cell_id']
LAW = ASSIGNMENT['law']['text']
TEMPLATE_ID = LAW_ID + '@' + ACTOR

PHRASES = [
    'pathway or lane provided for bicycles, electric bicycles or electric scooters',
    'yield the right-of-way to any person riding a bicycle',
    'yield the right-of-way to any person riding an electric bicycle',
    'yield the right-of-way to any person riding an electric scooter',
    'yield the right-of-way to a qualifying pedestrian on the pathway or lane',
    'enter within a pathway or lane',
    'stop within a pathway or lane',
    'stand within a pathway or lane',
    'park within a pathway or lane',
    'drive within a pathway or lane',
    'entering or exiting an alley or driveway',
    'operating or parking a disabled vehicle',
    'avoid conflict with other traffic',
    'performance of official duties',
    'compliance with the directions of a police officer',
    'in an emergency',
    'pedestrian as provided in subsection 6 of NRS 484B.297',
]

CLAUSES = [
    '(a) When entering or exiting an alley or driveway',
    '(b) When operating or parking a disabled vehicle',
    '(c) To avoid conflict with other traffic',
    '(d) In the performance of official duties',
    '(e) In compliance with the directions of a police officer',
    '(f) In an emergency',
]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assert len(PHRASES) == len(PLAN['requirement_dispositions']) == 17
    assert all(clause in LAW for clause in CLAUSES)
    relevance = {
        'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{
            'law_id': LAW_ID, 'quote': LAW, 'applies_to': [ACTOR],
            'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'The selected motor-vehicle driver faces the source yield and facility-use duties; physical qualification remains for original evidence review.'
        }], 'borderline_excluded': [],
    }
    judgments = [{'phrase': phrase,
                  'note': PLAN['requirement_dispositions'][index]['evidence_or_gap']}
                 for index, phrase in enumerate(PHRASES)]
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
        'quote': LAW, 'status': 'draft',
        'structure': {
            'law_id': LAW_ID,
            'activation': {'condition': 'A qualifying bicycle pathway or lane and relevant subject or vulnerable road user are present.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Yield to covered riders or qualifying pedestrians and avoid the five prohibited facility acts unless a listed exception applies.'},
            'exceptions': [{'source_clause': clause,
                            'description': 'Original source context and necessity require independent review.'}
                           for clause in CLAUSES],
            'timing': ASSIGNMENT['summary']['timing_requirements'],
            'judgment_calls_needed': judgments,
        },
        'parameter_refs': [{'name': 'requested_statutory_branch',
                            'kind': 'controller', 'unit': 'categorical',
                            'description': 'Which exact source-grounded comparison branch the construction requests; observed conduct remains trace-only.'}],
    }
    observed = []
    for index, item in enumerate(judgments):
        observed.append(save(PROPOSALS / f'judgment_observables_{index:02d}.json', {
            'template_id': TEMPLATE_ID, 'phrase': item['phrase'],
            'note': item['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': [
                    {'name': 'kin.position', 'unit': 'm',
                     'description': 'Original frame-indexed motor-vehicle pose for the specific statutory topic.'},
                    {'name': 'rel.occupies', 'unit': 'structured',
                     'description': 'Original body-to-facility occupancy relation for the specific statutory topic.'},
                ],
                'context_inputs': [
                    {'name': 'requested_exception_context', 'unit': 'structured',
                     'description': 'Requested source context only; observed exception and right-of-way facts require independent review.'},
                ],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [
                    {'name': 'kin.position', 'unit': 'm',
                     'description': 'Retain the original same-tick body pose.'},
                    {'name': 'rel.occupies', 'unit': 'structured',
                     'description': 'Retain original facility occupancy and map reference.'},
                    {'name': 'camera_frame_join', 'unit': 'structured',
                     'description': 'Retain synchronized source video frames for later original-pixel review.'},
                ],
                'limitations': [item['note'],
                                'Selected source packets and case-specific saved measurements are specified in each exact measurement contract; synthetic CPU evidence is not a legal verdict.'],
            },
        }))
    bindings = {
        'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['Authored facility and alley geometry are software construction inputs; original Native designation remains unresolved.'],
        'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
        'context_refs': [],
        'fixed_parameters': [
            {'name': 'assignment_identity', 'value': LAW_ID + '@' + CELL_ID,
             'rationale': 'All selected cases preserve the frozen law, actor and cell.'},
        ],
        'variable_parameters': [
            {'name': 'requested_statutory_branch', 'kind': 'controller',
             'range_or_domain': ['baseline'] + [c['case_id'].rsplit('__', 1)[-1] for c in PLAN['cases']],
             'used_by_laws': [LAW_ID]},
        ],
    }
    cases_path = PROPOSALS / 'cases.json'
    cases = json.loads(cases_path.read_text())
    current = {c['case_id']: c for c in cases['cases'] if c['case_id'] != ROOT.name + '__baseline'}
    assert set(current) == {c['case_id'] for c in PLAN['cases']}
    pair_by_case = {cid: comparison for comparison in PLAN['comparisons']
                    for cid in comparison['case_ids']}
    assert set(pair_by_case) == set(current)
    unresolved = [j['phrase'] for j in judgments]
    baseline_id = ROOT.name + '__baseline'
    baseline = {
        'case_id': baseline_id, 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Neutral shared comparator definition; no delivery recording or legal finding.',
        'variable_assignments': {'requested_statutory_branch': {
            'kind': 'controller', 'value': 'baseline', 'unit': 'categorical'}},
        'unresolved_judgment_calls': unresolved,
        'recording_description': current[next(iter(current))]['recording_description'],
    }
    enriched = [baseline]
    for case in current.values():
        cid = case['case_id']
        suffix = cid.rsplit('__', 1)[-1]
        comparison = pair_by_case[cid]
        case.update(
            target_type='boundary_probe', target_law_id=LAW_ID,
            rationale=f'Exact source-bound CPU construction for {suffix}; physical and legal findings remain unclaimed.',
            variable_assignments={'requested_statutory_branch': {
                'kind': 'controller', 'value': suffix, 'unit': 'categorical'}},
            unresolved_judgment_calls=unresolved,
            paired_probe_id=comparison['comparison_id'],
            deliberate_differences=['requested_statutory_branch'],
            probe={'primary_variable': 'requested_statutory_branch',
                   'comparison_or_standard': comparison['comparison_id'],
                   'target_value_or_branch': suffix},
        )
        enriched.append(case)
    cases.update(cell_id=CELL_ID, actor=ACTOR, status='draft',
                 sweep_specs=[{
                     'sweep_id': 'C10052-original-source-judgment',
                     'target_law_id': LAW_ID,
                     'judgment_refs': judgments,
                     'rationale': 'The 24 exact controlled CPU cases cover the source branches. Actual right-of-way, facility designation and exception necessity require original Native and legal review; no synthetic judgment cutoff is asserted.',
                     'status': 'incomplete',
                     'missing_inputs': ['Original Native actor and facility readback, original camera pixels, and independent legal source qualification.'],
                 }], sweeps_expanded=True, cases=enriched)
    stages = {
        'relevance_batch': save(PROPOSALS / 'relevance-batch.json', relevance),
        'relevance': save(PROPOSALS / 'relevance.json', relevance),
        'template': save(PROPOSALS / 'template.json', template),
        'judgment_observables': observed,
        'bindings': save(PROPOSALS / 'bindings.json', bindings),
        'cases': save(cases_path, cases),
    }
    save(PROPOSALS / 'semantic-index.json', {
        'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
        'stages': stages,
    })
    print('Built 17 draft judgment stages and 24 selected semantic cases')


if __name__ == '__main__':
    main()
