"""Independently bind the exact law branches to selected CPU source proofs."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LINKED = REPO / 'work/heldout__C293604__NRS-484B-250-3__motor_vehicle_driver/gpu-queue.json'

def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def audit(folder=HERE, linked_path=LINKED, *, matrix=None, queue=None):
    folder = Path(folder)
    assignment_path = REPO / 'inputs' / folder.name / 'assignment.json'
    assignment = json.loads(assignment_path.read_text())
    law = assignment['law']['text']
    for phrase in ('highway which ends at the intersection', 'through highway',
                   'approximately the same time', 'yield the right-of-way',
                   'official traffic-control devices', 'opposite directions',
                   'intending to or is making a left turn', 'subsection 4'):
        require(phrase in law, 'Frozen statutory phrase missing: ' + phrase)
    plan_path = folder / 'case-plan.json'
    manifest_path = folder / 'execution-manifest.json'
    matrix_path = folder / 'qualitative-source-matrix-proof.json'
    queue_path = folder / 'gpu-queue.json'
    dispatch_path = folder / 'comparison-dispatch-proof.json'
    queued_path = folder / 'queued-comparison-proof.json'
    plan = json.loads(plan_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    matrix = matrix if matrix is not None else json.loads(matrix_path.read_text())
    queue = queue if queue is not None else json.loads(queue_path.read_text())
    dispatch = json.loads(dispatch_path.read_text())
    queued = json.loads(queued_path.read_text())
    linked = json.loads(Path(linked_path).read_text())
    cases = [row['case_id'] for row in plan['cases']]
    comparisons = {row['comparison_id']: row['case_ids'] for row in plan['comparisons']}
    require(len(cases) == len(set(cases)) == 9, 'Exact local law cases changed')
    require(set(cases) == {row['case_id'] for row in manifest['cases']} ==
            {row['case_id'] for row in queue['cases']}, 'Local plan/manifest/queue cases differ')
    require(queue['execution_manifest_sha256'] == sha(manifest_path) and
            queue['case_plan_sha256'] == sha(plan_path), 'Local queue source hashes differ')
    require(set(comparisons) == {row['comparison_id'] for row in queue['comparisons']} ==
            {row['comparison_id'] for row in dispatch['comparisons']} ==
            {row['comparison_id'] for row in queued['comparisons']},
            'Local comparison dispatch coverage differs')
    require(dispatch['manifest_sha256'] == sha(manifest_path) and
            dispatch['case_plan_sha256'] == sha(plan_path) and
            queued['queue_sha256'] == sha(queue_path),
            'Comparison proof source hashes differ')
    require(all(row['exit_code'] == 0 for row in dispatch['comparisons'] +
                queued['comparisons']), 'Comparison dispatch did not pass')
    expected = {
        'ending_through_yield_order': ('same_arrival_ending_yields', 'same_arrival_ending_enters_first'),
        'arrival_timing_applicability': ('same_arrival_ending_yields', 'separated_arrival'),
        'official_control_exception': ('same_arrival_ending_yields', 'official_device_control'),
        'yield_release_delay_sweep': ('yield_release_delay-0000', 'yield_release_delay-0001', 'yield_release_delay-0002'),
        'official_device_red_green': ('official_device_control', 'official_device_green_phase'),
        'ending_vs_continuing_highway': ('same_arrival_ending_yields', 'continuing_highway'),
    }
    require(set(comparisons) == set(expected), 'Exact statutory comparisons changed')
    for name, suffixes in expected.items():
        require(comparisons[name] == [folder.name + '__' + suffix for suffix in suffixes],
                'Statutory comparison members differ: ' + name)
    require(matrix['law_id'] == assignment['law_id'] and
            matrix['ending_case'] == folder.name + '__same_arrival_ending_yields' and
            matrix['official_case'] == folder.name + '__official_device_control' and
            matrix['native_capture_claimed'] is False and
            matrix['legal_judgment_claimed'] is False,
            'Selected original-source matrix identity or claim differs')
    require(matrix.get('arrival_timing') and matrix.get('release_timing') and
            matrix.get('turn_release_timing') and matrix.get('highway_continuity') and
            matrix.get('official_phase') and matrix.get('shallow_turn'),
            'Selected original-source matrix omits a statutory contrast')
    require(linked['assignment_id'] ==
            'heldout__C293604__NRS-484B-250-3__motor_vehicle_driver' and
            len(linked['cases']) == 6 and len(linked['comparisons']) == 3,
            'Linked opposing-left source queue changed')
    linked_cases = {row['case_id'] for row in linked['cases']}
    require(matrix['turn_case'] in linked_cases and matrix['hold_case'] in linked_cases,
            'Linked opposing-left selected source cases differ')
    return {'format': 'worker-independent-full-law-delivery-audit',
            'assignment_id': folder.name, 'law_source_sha256': sha(assignment_path),
            'case_plan_sha256': sha(plan_path), 'manifest_sha256': sha(manifest_path),
            'source_matrix_sha256': sha(matrix_path), 'queue_sha256': sha(queue_path),
            'linked_queue_sha256': sha(linked_path),
            'local_selected_cases': len(cases),
            'local_comparisons': len(comparisons),
            'linked_opposing_left_cases': len(linked['cases']),
            'linked_opposing_left_comparisons': len(linked['comparisons']),
            'software_source_binding_passed': True,
            'physical_or_legal_acceptance_claimed': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = audit()
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print('independent_full_law_delivery_source_audit_passed')
