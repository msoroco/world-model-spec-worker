"""Reconcile C405647 delivery drafts with the frozen NRS 484B.267(1)(a) clause."""
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SOURCE = Path('inputs') / ASSIGNMENT / 'assignment.json'
PLAN = ROOT / 'case-plan.json'
RESULT = ROOT / 'result.json'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    plan = json.loads(PLAN.read_text())
    result = json.loads(RESULT.read_text())
    clause = source['law_record']['text']
    assert plan['source_law']['text'] == clause
    canonical_law = json.dumps(source['law_record'], sort_keys=True, separators=(',', ':'))
    assert hashlib.sha256(canonical_law.encode()).hexdigest() == plan['source_law']['sha256']
    assert 'authorized emergency vehicle or an official vehicle of a regulatory agency' in clause
    assert 'except when otherwise directed by a law enforcement officer' in clause
    assert 'flashing lights meeting the requirements of subsection 3 of NRS 484A.480' in clause

    official_branch = 'official_regulatory_vehicle_approach'
    official_ids = [f'{ASSIGNMENT}__official_1', f'{ASSIGNMENT}__official_2']
    if not any(d['branch'] == official_branch for d in plan['requirement_dispositions']):
        plan['requirement_dispositions'].append({
            'requirement': source['law_id'],
            'source': source['law_record']['source'],
            'branch': official_branch,
            'status': 'selected_required',
            'case_ids': official_ids,
            'evidence_or_gap': 'The official vehicle alternative appears in the exact clause but has no verified agency status, qualifying lamps, immediate approach, Native construction, saved measurement, or CPU delivery proof. These cases remain unselected planning targets.'
        })
        base = next(c for c in plan['cases'] if c['case_id'].endswith('__witness_1'))
        for idx, requested in enumerate(('yield to the immediately approaching official regulatory vehicle', 'maintain a conflicting course during the same immediate approach')):
            case = copy.deepcopy(base)
            case['case_id'] = official_ids[idx]
            case['source_branch'] = official_branch
            case['comparison_variable'] = 'official_vehicle_yield'
            case['physical_target'] = requested
            case['controller']['requested_behavior'] = requested
            case['world_setup']['activation_conditions_to_verify'] = [
                'the approaching vehicle is an official vehicle of a regulatory agency',
                'its immediate approach to the subject vehicle is established from saved relative motion',
                'its actual flashing lights meet the incorporated NRS 484A.480(3) requirements',
                'the subject is the driver of a different vehicle',
                'absence or content and timing of any contrary law enforcement officer direction is established'
            ]
            plan['cases'].append(case)
        plan['comparisons'].append({
            'comparison_id': f'{ASSIGNMENT}__official_comparison',
            'case_ids': official_ids,
            'deliberate_differences': ['official_vehicle_yield'],
            'fixed_conditions': [
                'frozen road/travel/emergency_vehicle cell and motor_vehicle_driver actor',
                'same official regulatory vehicle, agency status, lamp operation and approach trace',
                'same map, non-target actors, rate, cameras and observation windows; exact sameness pending construction'
            ]
        })

    for case in plan['cases']:
        if case['source_branch'] == 'when otherwise directed by a law enforcement officer':
            case['world_setup']['activation_conditions_to_verify'].append(
                'the officer identity, direction content, recipient and time must be observed; officer presence alone does not establish the exception'
            )
            if case['case_id'].endswith('__exception_1_2'):
                case['physical_target'] = 'hold the same immediate approach while an identified law enforcement officer directs this driver otherwise, recording direction content and timing'
                case['controller']['requested_behavior'] = case['physical_target']

    plan['unresolved_judgment_calls'] = [
        "'immediate approach' remains a value-free physical observation and later legal interpretation; do not impose an authored distance or time threshold",
        'NRS 484A.480(3) is incorporated by reference; exact lamp qualification requires the incorporated source and operation evidence. Lamp color alone does not prove it.',
    ]
    for case in plan['cases']:
        case['unresolved_judgment_calls'] = list(plan['unresolved_judgment_calls'])
    plan['activation_conditions'] = [
        'an authorized emergency vehicle or an official vehicle of a regulatory agency immediately approaches the subject vehicle',
        'the approaching vehicle actually uses flashing lights satisfying incorporated NRS 484A.480(3)',
        'the subject drives a different vehicle',
        'a contrary law enforcement officer direction, if any, is distinguished by officer authority, content, recipient and timing',
    ]
    plan['witness_branches'] = ['authorized_emergency_vehicle_approach']
    plan['statutory_branch_review'] = {
        'source_path': str(SOURCE),
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'law_text_sha256': plan['source_law']['sha256'],
        'alternatives': [
            {'name': 'authorized_emergency_vehicle_approach', 'basis': 'an authorized emergency vehicle', 'status': 'unselected_cpu_unproven'},
            {'name': official_branch, 'basis': 'or an official vehicle of a regulatory agency', 'status': 'unselected_cpu_unproven'},
        ],
        'common_activation': 'immediate approach and actual qualifying flashing-light use; subject is the driver of every other vehicle',
        'exception': 'when otherwise directed by a law enforcement officer',
        'obligation': 'Yield the right-of-way.',
        'summary_conflicts': [
            'The recovered summary treats red or blue lamp color as the observable for statutory qualification, but the frozen clause incorporates NRS 484A.480(3). Color alone is insufficient; the referenced definition and operation must be sourced.',
            'The recovered summary describes continuous yield throughout the approach; the exact clause states the duty upon immediate approach without a separately stated duration or numerical onset threshold.'
        ],
        'unresolved': [
            'The incorporated NRS 484A.480(3) definition is not supplied as an exact frozen source in this assignment.',
            'Official regulatory agency vehicle status and officer authority need source-backed setup and saved evidence.',
            'Immediate approach and right-of-way outcomes require Native motion and control observations; no legal verdict follows from requested behavior.'
        ]
    }
    result['planned_case_count'] = len(plan['cases'])
    result['comparison_count'] = len(plan['comparisons'])
    result['unresolved_branch_count'] = len(plan['requirement_dispositions'])
    result['source_law_review'] = 'Exact clause reviewed: both approaching-vehicle alternatives, common lamp/approach conditions, yield duty, and officer-direction exception inventoried; incorporated lamp definition and all CPU delivery proofs remain open.'
    result['reason'] = 'Exact clause review now includes the official regulatory vehicle alternative and officer-direction evidence. Incorporated NRS 484A.480(3) source, executable Native construction, four candidates per case, exact offline and compatibility proofs, saved fixtures and independent audits remain absent.'
    plan['blockers'] = [result['reason']]
    plan['readiness_limitation'] = 'Source-reviewed planning only. All cases remain unselected; no physical activation or legal outcome is measured.'
    write(PLAN, plan)
    write(RESULT, result)


if __name__ == '__main__':
    main()
