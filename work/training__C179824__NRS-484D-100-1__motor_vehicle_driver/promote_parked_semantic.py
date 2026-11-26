"""Bind source-reviewed parked exception drafts to canonical semantic cases."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
BRANCH = 'Referenced parked-vehicle exception and NRS 484D.165(1),(3),(4)'


def read(name):
    return json.loads((HERE/name).read_text())


def write(name, value):
    path = HERE/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    drafts = read('proposals/parked-exception-cases-draft.json')['cases']
    assert len(drafts) == 2
    proposal = read('proposals/cases.json')
    plan = read('case-plan.json')
    proposal_ids = {case['case_id'] for case in proposal['cases']}
    plan_ids = {case['case_id'] for case in plan['cases']}
    for draft in drafts:
        case_id = draft['case_id']
        suffix = case_id.removeprefix(ASSIGNMENT+'__')
        assert suffix != case_id
        construction = HERE/'draft-parked-cases'/suffix/'primary/construction.json'
        assert construction.is_file()
        for candidate in ('primary', 'fallback1'):
            log = HERE.parents[1]/'.runtime-work/c179824'/(
                'parked-offline-'+suffix[-1]+'-'+candidate)/'offline.log'
            assert log.is_file() and 'OK' in log.read_text()
        selected = dict(draft)
        selected['selection_targets'] = ['full-train']
        selected['source_branch'] = BRANCH
        selected['status'] = 'selected_cpu_draft_physical_unverified'
        if case_id not in proposal_ids:
            proposal['cases'].append(selected)
            proposal_ids.add(case_id)
        if case_id not in plan_ids:
            plan['cases'].append({
                'case_id': case_id, 'target_law_id': 'NRS-484D-100-1',
                'kind': 'planned_only', 'source_branch': BRANCH,
                'physical_target': draft['rationale'],
                'comparison_variable': 'requested_lamp_setting_on',
                'requested_not_measured': True, 'selection_targets': ['full-train'],
                'cpu_native_draft': {
                    'construction': f'draft-parked-cases/{suffix}/primary/construction.json',
                    'construction_sha256': sha(construction),
                    'status': 'offline_and_synthetic_finalizer_passed_public_receipt_pending'},
                'probe': draft['probe'], 'disposition_index': 1,
            })
            plan_ids.add(case_id)
        write(f'cases/{suffix}/measurement-contract.json', {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{
                'disposition_index': 1, 'requirement': 'NRS-484D-100-1',
                'source': 'NRS 484D.100(1)', 'output_key': 'lamp_device_measurement',
                'method': 'reviewed_measure', 'value_type': 'object',
                'kind': 'measured', 'inputs': [
                    'parked-trace.jsonl', 'parked-exception-review.json',
                    'nrs-484d-165-source.json', 'parked-highway-review.json',
                    'parked-status-review.json', 'visibility-trace.jsonl',
                    'vehicle-lamps.jsonl', 'video_frames.jsonl', 'road.xodr',
                    'visibility-context.json', 'visibility-pixel-review.json',
                    'civil-clock.json', 'civil-time-review.json',
                    'sun-event-source.json', 'location-source.json',
                    'lamp-context.json', 'lamp-source-review.json',
                    'highway-review.json', 'vehicle-class-review.json',
                    'device-content-review.json', 'device-authority-review.json',
                    'device-placement-review.json', 'device-timing-review.json',
                    'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                    'driver_reference.mkv'],
            }],
            'negative': {'remove': ['parked-status-review.json'],
                         'error_contains': 'Missing required source: parked-status-review.json'},
        })
    disposition = plan['requirement_dispositions'][1]
    disposition.update(branch=BRANCH, status='selected_required',
                       case_ids=[case['case_id'] for case in drafts],
                       evidence_or_gap=(
                           'Exact travel-to-park Native drafts, pinned offline checks and '
                           'synthetic source-gated finalizer proofs pass. Original shoulder '
                           'motion, light, class equipment and exception review remain pending.'))
    comparison_id = drafts[0]['paired_probe_id']+'__comparison'
    if not any(c['comparison_id'] == comparison_id for c in plan['comparisons']):
        plan['comparisons'].append({
            'comparison_id': comparison_id,
            'case_ids': [case['case_id'] for case in drafts],
            'deliberate_differences': ['requested_lamp_setting_on'],
            'fixed_conditions': [
                'same frozen Nevada paved-road travel cell and actor',
                'same four cameras, 20 Hz, 600-frame acquisition',
                'same source-reviewed shoulder, clock and visibility requirements'],
        })
    plan['full_law_review']['coverage_gap'] = (
        'Civil-time, visibility and parked exception constructions have offline '
        'CPU proofs; exact public/saved and delivery integration, class-specific '
        'sufficiency, original Native pixels and physical/legal review remain pending.')
    write('proposals/cases.json', proposal)
    write('case-plan.json', plan)
    index = read('proposals/semantic-index.json')
    index['stages']['cases']['sha256'] = sha(HERE/'proposals/cases.json')
    write('proposals/semantic-index.json', index)
    print(json.dumps({'selected_parked_cases': len(drafts),
                      'parked_comparisons': 1, 'physical_acceptance_claimed': False},
                     sort_keys=True))


if __name__ == '__main__':
    main()
