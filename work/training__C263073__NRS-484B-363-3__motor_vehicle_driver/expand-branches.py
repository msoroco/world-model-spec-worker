"""Expand the exact school-zone law into source-specific selected case plans."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
NEW = (
    ('exception_a', '(a) no children present', 'same active school context and U-turn; no child present', 'child presence'),
    ('exception_b', '(b) school not in session', 'same local clock hour on a non-session school day; U-turn with child present', 'school session day'),
    ('exception_c', '(c) half-hour operation interval', 'school day outside the statutory half-hour operation window; U-turn with child present', 'school operation interval and civil time'),
    ('exception_d', '(d) operational beacon, class hours, nonflashing yellow lights', 'same class hours and operational beacon; yellow lights not flashing; U-turn with child present', 'beacon yellow-light state'),
    ('exception_e_reference', '(e) no operational beacon, sign indicates limit in effect', 'no operational beacon and sign indicates school speed limit in effect; U-turn with child present', 'beacon operational state'),
    ('exception_e', '(e) no operational beacon, sign indicates limit not in effect', 'same non-operational beacon and sign indicates school speed limit not in effect; U-turn with child present', 'sign speed-limit indication'),
)

def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def main():
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    base = plan['cases'][1]
    existing = {case['case_id'] for case in plan['cases']}
    for suffix, branch, target, variable in NEW:
        cid = AID + '__' + suffix
        if cid in existing:
            continue
        case = copy.deepcopy(base)
        case.update(case_id=cid, source_branch=branch, physical_target=target,
                    comparison_variable=variable, requested_not_measured=True,
                    construction='native/bundles/' + suffix + '/construction.json',
                    offline_passed=False,
                    candidate_risk={'status':'physical',
                        'reason':'Original driven path may not track authored school-zone envelope; matched compact-vehicle fallback'},
                    candidates=['fallback1'])
        plan['cases'].append(case)
    controlled_2 = AID + '__controlled_2'
    e_ref = AID + '__exception_e_reference'
    comparisons = plan['comparisons'][:1]
    for suffix, branch, target, variable in NEW:
        if suffix == 'exception_e_reference':
            continue
        cid = AID + '__' + suffix
        comparison = copy.deepcopy(comparisons[0])
        comparison['comparison_id'] = AID + '__' + suffix + '_comparison'
        comparison['case_ids'] = [e_ref if suffix == 'exception_e' else controlled_2, cid]
        comparison['deliberate_differences'] = [variable]
        comparison['fixed_conditions'] = [
            'frozen cell, role, road geometry, U-turn controller and 30-second four-camera capture',
            'all independent school-context source topics outside the named comparison variable',
            'source records remain original and legal applicability is independently reviewed',
        ]
        comparisons.append(comparison)
    plan['comparisons'] = comparisons
    mapping = {
        0: [AID + '__controlled_1', controlled_2],
        1: [controlled_2, AID + '__exception_a'],
        2: [controlled_2, AID + '__exception_b'],
        3: [controlled_2, AID + '__exception_c'],
        4: [controlled_2, AID + '__exception_d'],
        5: [e_ref, AID + '__exception_e'],
    }
    for i, disposition in enumerate(plan['requirement_dispositions']):
        disposition['case_ids'] = mapping[i]
        disposition['status'] = 'selected_required' if i == 0 else 'planned_pending_cpu_proofs'
        if i:
            disposition['evidence_or_gap'] = 'Exact exception-specific case and controlled source comparison planned; CPU construction and proofs pending.'
    plan['runtime_uncertainties'] = [
        'Two active-prohibition Native bundles passed exact scoped CPU gate, but exception-specific branches are expanding.',
        'Each exception requires an independently source-bound physical/context distinction and controlled comparison.',
        'No actual CARLA execution, original pixel review or legal exception verdict has occurred.',
    ]
    plan['blockers'] = ['Six new exception-context Native cases and five comparisons require construction and full CPU proofs.']
    write(plan_path, plan)
    result_path = ROOT / 'result.json'
    result = json.loads(result_path.read_text())
    result['planned_case_count'] = len(plan['cases'])
    result['cases_planned'] = len(plan['cases'])
    result['cases_selected'] = 2
    result['comparison_audits_passed'] = 1
    result['unresolved_branch_count'] = 5
    write(result_path, result)
    print(json.dumps({'cases':len(plan['cases']),'comparisons':len(plan['comparisons']),
                      'pending_exception_branches':5}))

if __name__ == '__main__':
    main()
