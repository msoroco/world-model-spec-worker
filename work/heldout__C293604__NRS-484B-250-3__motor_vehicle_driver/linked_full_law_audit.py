"""Independent CPU source binding for the NRS 484B.250(3) linked left-turn branch."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / 'work/heldout__C293604__NRS-484B-250-3__motor_vehicle_driver'
MAIN = ROOT / 'work/heldout__C111294__NRS-484B-250-3__motor_vehicle_driver'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read(folder, name):
    return json.loads((folder / name).read_text())


def audit(local=None, main=None, main_proof=None, assignment=None):
    local = local or {'manifest': read(LOCAL, 'execution-manifest.json'),
                      'plan': read(LOCAL, 'case-plan.json'),
                      'queue': read(LOCAL, 'gpu-queue.json'),
                      'proposal': read(LOCAL, 'proposals/cases.json')}
    main = main or {'manifest': read(MAIN, 'execution-manifest.json'),
                    'plan': read(MAIN, 'case-plan.json'),
                    'queue': read(MAIN, 'gpu-queue.json')}
    main_proof = main_proof or read(MAIN, 'full-law-source-audit-proof.json')
    assignment = assignment or read(LOCAL, 'assignment.json')
    law = assignment['law']['text']
    clauses = {
        'approximately the same time': ('arrival_timing_applicability', 'same_arrival_ending_yields', 'separated_arrival'),
        'highway which ends at the intersection': ('ending_vs_continuing_highway', 'same_arrival_ending_yields', 'continuing_highway'),
        'yield the right-of-way': ('ending_through_yield_order', 'same_arrival_ending_yields', 'same_arrival_ending_enters_first'),
        'official traffic-control devices': ('official_device_red_green', 'official_device_control', 'official_device_green_phase'),
        'approaching each other from opposite directions': ('opposing_left_shallow_vs_orthogonal', 'opposing_left_turn', 'opposing_left_shallow_turn'),
        'intending to or is making a left turn': ('opposing_left_intent_vs_making', 'opposing_left_turn', 'opposing_left_intent_hold'),
    }
    proposal_phrases = {row['phrase'] for row in local['proposal']['sweep_specs'][0]['judgment_refs']}
    proposal_phrases |= {row['phrase'] for row in local['proposal']['sweep_specs'][1]['judgment_refs']}
    if proposal_phrases != set(clauses) or any(phrase not in law for phrase in clauses):
        raise ValueError('Full-law phrase coverage changed')
    if assignment['cell']['maneuver'] != 'left_turn' or assignment['cell']['layout'] != 't_intersection':
        raise ValueError('Linked left-turn cell identity changed')
    if main_proof['linked_queue_sha256'] != digest(LOCAL / 'gpu-queue.json') or not main_proof['software_source_binding_passed']:
        raise ValueError('Main full-law proof does not bind linked queue')
    if main_proof['manifest_sha256'] != digest(MAIN / 'execution-manifest.json') or main_proof['queue_sha256'] != digest(MAIN / 'gpu-queue.json'):
        raise ValueError('Main full-law source proof is stale')
    if local['queue']['execution_manifest_sha256'] != digest(LOCAL / 'execution-manifest.json') or local['queue']['case_plan_sha256'] != digest(LOCAL / 'case-plan.json'):
        raise ValueError('Linked queue source binding changed')
    linked_id = local['manifest']['assignment_id']
    main_id = main['manifest']['assignment_id']
    if linked_id == main_id or linked_id != assignment['assignment_id']:
        raise ValueError('Cross-cell assignment identity changed')
    selected = {row['case_id'] for row in local['manifest']['cases']}
    planned = {row['case_id'] for row in local['plan']['cases']}
    queued = {row['case_id'] for row in local['queue']['cases']}
    if len(selected) != 6 or selected != planned or selected != queued:
        raise ValueError('Linked selected case coverage differs')
    if any(len(row['candidates']) != 3 for row in local['manifest']['cases']):
        raise ValueError('Linked fallback coverage differs')
    comparisons = {row['comparison_id']: row for row in local['plan']['comparisons']}
    dispatched = {row['comparison_id']: row for row in local['queue']['comparisons']}
    if set(comparisons) != set(dispatched) or len(comparisons) != 3:
        raise ValueError('Linked comparison dispatch coverage differs')
    main_cases = {row['case_id'] for row in main['manifest']['cases']}
    main_comparisons = {row['comparison_id']: row for row in main['plan']['comparisons']}
    evidence = []
    for phrase, (comparison, first, second) in clauses.items():
        folder_id, cases, comparisons_for_cell = (linked_id, selected, comparisons) if phrase.startswith(('approaching', 'intending')) else (main_id, main_cases, main_comparisons)
        expected = {folder_id + '__' + first, folder_id + '__' + second}
        row = comparisons_for_cell.get(comparison)
        if not row or not expected <= set(row['case_ids']) or not expected <= cases:
            raise ValueError('Law clause lacks exact selected comparison: ' + phrase)
        if folder_id == linked_id and (not dispatched[comparison].get('audit_command') or comparison not in dispatched[comparison]['audit_command']):
            raise ValueError('Linked comparison has no exact audit command')
        evidence.append({'phrase': phrase, 'assignment_id': folder_id,
                         'comparison_id': comparison, 'case_ids': sorted(expected)})
    if main_proof.get('physical_or_legal_acceptance_claimed') is not False:
        raise ValueError('Source audit cannot claim legal or physical acceptance')
    return {'format': 'worker-linked-full-law-source-audit',
            'law_id': assignment['law_id'], 'linked_assignment_id': linked_id,
            'main_assignment_id': main_id, 'clauses': evidence,
            'linked_manifest_sha256': digest(LOCAL / 'execution-manifest.json'),
            'linked_queue_sha256': digest(LOCAL / 'gpu-queue.json'),
            'main_full_law_proof_sha256': digest(MAIN / 'full-law-source-audit-proof.json'),
            'software_source_binding_passed': True,
            'canonical_sweep_completion_claimed': False,
            'physical_or_legal_acceptance_claimed': False}


def selftest():
    result = audit()
    assert len(result['clauses']) == 6
    local = {'manifest': read(LOCAL, 'execution-manifest.json'), 'plan': read(LOCAL, 'case-plan.json'),
             'queue': read(LOCAL, 'gpu-queue.json'), 'proposal': read(LOCAL, 'proposals/cases.json')}
    corrupted = deepcopy(local)
    corrupted['queue']['comparisons'].pop()
    try:
        audit(local=corrupted)
    except ValueError as error:
        assert 'comparison dispatch' in str(error)
    else:
        raise AssertionError('Missing linked comparison was accepted')
    corrupted = deepcopy(local)
    corrupted['plan']['comparisons'][0]['case_ids'].pop()
    try:
        audit(local=corrupted)
    except ValueError as error:
        assert 'exact selected comparison' in str(error)
    else:
        raise AssertionError('Changed selected comparison was accepted')
    return result


if __name__ == '__main__':
    result = selftest()
    output = Path(__file__).with_name('linked-full-law-source-proof.json')
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'clauses': len(result['clauses']), 'negative_checks': 2,
                      'proof_sha256': digest(output)}))
