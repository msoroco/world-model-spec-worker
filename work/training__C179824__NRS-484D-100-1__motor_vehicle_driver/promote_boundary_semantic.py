"""Bind source-grounded civil and visibility drafts to exact selected requirements.

This only selects CPU-proven construction plans. Physical and legal outcomes stay
unverified, and execution entries require their own compatibility receipts.
"""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def read(name):
    return json.loads((HERE/name).read_text())


def write(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    draft = read('proposals/boundary-cases-draft.json')['cases']
    receipt = read('draft-boundary-offline-receipt.json')
    assert receipt['all_passed'] and len(receipt['cases']) == 18
    for item in receipt['cases']:
        assert item['exit_code'] == 0
        assert sha(HERE/item['offline_log']) == item['offline_log_sha256']
    proposal = read('proposals/cases.json')
    plan = read('case-plan.json')
    by_id = {case['case_id']: case for case in proposal['cases']}
    plan_ids = {case['case_id'] for case in plan['cases']}
    groups = {}
    for case in draft:
        suffix = case['case_id'].removeprefix(ASSIGNMENT+'__')
        assert suffix != case['case_id']
        if suffix.startswith(('minutes_after_sunset_', 'minutes_before_sunrise_')):
            branch = '(a) Half-hour sunset and sunrise interval'
            disposition = 2
        else:
            branch = '(b) Other-time person and vehicle discernibility at 1,000 feet'
            disposition = 3
        selected = dict(case)
        selected['selection_targets'] = ['full-train']
        selected['source_branch'] = branch
        selected['status'] = 'selected_cpu_draft_physical_unverified'
        if case['case_id'] not in by_id:
            proposal['cases'].append(selected)
            by_id[case['case_id']] = selected
        else:
            assert by_id[case['case_id']] == selected
        if case['case_id'] not in plan_ids:
            plan['cases'].append({
                'case_id': case['case_id'], 'target_law_id': 'NRS-484D-100-1',
                'kind': 'planned_only', 'source_branch': branch,
                'physical_target': case['rationale'],
                'comparison_variable': case['probe']['primary_variable'],
                'requested_not_measured': True, 'selection_targets': ['full-train'],
                'cpu_native_draft': {'construction':
                    f'draft-boundary-cases/{suffix}/primary/construction.json',
                    'construction_sha256': sha(HERE/'draft-boundary-cases'/suffix/'primary/construction.json'),
                    'status': 'offline_passed_public_receipt_pending'},
                'probe': case['probe'], 'disposition_index': disposition,
            })
            plan_ids.add(case['case_id'])
        groups.setdefault(case['paired_probe_id'], []).append(case)
        contract = {
            'format': 'worker-measurement-contract', 'case_id': case['case_id'],
            'requirements': [{
                'disposition_index': disposition,
                'requirement': 'NRS-484D-100-1', 'source': 'NRS 484D.100(1)',
                'output_key': 'civil_visibility_measurement',
                'method': 'reviewed_measure', 'value_type': 'object',
                'kind': 'measured',
                'inputs': [
                    'visibility-trace.jsonl', 'video_frames.jsonl', 'road.xodr',
                    'visibility-context.json', 'visibility-pixel-review.json',
                    'civil-clock.json', 'civil-time-review.json',
                    'sun-event-source.json', 'location-source.json',
                    'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                    'driver_reference.mkv'],
            }],
            'negative': {'remove': ['sun-event-source.json' if disposition == 2 else
                                    'visibility-pixel-review.json'],
                         'error_contains': 'Missing required source: '+
                         ('sun-event-source.json' if disposition == 2 else
                          'visibility-pixel-review.json')},
        }
        write(f'cases/{suffix}/measurement-contract.json', contract)
    assert len(groups) == 3 and all(len(rows) == 3 for rows in groups.values())
    for group, rows in groups.items():
        comparison_id = group+'__comparison'
        if not any(item['comparison_id'] == comparison_id for item in plan['comparisons']):
            plan['comparisons'].append({
                'comparison_id': comparison_id,
                'case_ids': [row['case_id'] for row in rows],
                'deliberate_differences': rows[0]['deliberate_differences'],
                'fixed_conditions': [
                    'same frozen Nevada paved-road travel cell and actor',
                    'same four cameras, 20 Hz, 600-frame acquisition',
                    'same lamp setting, target identities and source-review requirements',
                ],
            })
    for index, branch, identifiers in (
        (2, '(a) Half-hour sunset and sunrise interval',
         [c['case_id'] for c in draft if 'minutes_' in c['case_id']]),
        (3, '(b) Other-time person and vehicle discernibility at 1,000 feet',
         [c['case_id'] for c in draft if 'target_reference_distance_ft' in c['case_id']]),
    ):
        disposition_row = {
            'requirement': 'NRS-484D-100-1', 'source': 'NRS 484D.100(1)',
            'branch': branch, 'status': 'selected_required', 'case_ids': identifiers,
            'evidence_or_gap': 'Exact Native draft and pinned offline CPU proof exist; public diagnostic compatibility, original Native pixels and legal sufficiency remain unverified.',
        }
        if len(plan['requirement_dispositions']) == index:
            plan['requirement_dispositions'].append(disposition_row)
        else:
            assert plan['requirement_dispositions'][index] == disposition_row
    plan['full_law_review']['coverage_gap'] = (
        'Civil-time and 1,000-foot boundary Native drafts have pinned offline proofs; '
        'public compatibility, parked exceptions, class-specific sufficiency, '
        'original Native pixels and physical/legal acceptance remain unverified.')
    write('proposals/cases.json', proposal)
    write('case-plan.json', plan)
    index = read('proposals/semantic-index.json')
    index['stages']['cases']['sha256'] = sha(HERE/'proposals/cases.json')
    write('proposals/semantic-index.json', index)
    print(json.dumps({'selected_boundary_cases': len(draft),
                      'boundary_comparisons': len(groups),
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
