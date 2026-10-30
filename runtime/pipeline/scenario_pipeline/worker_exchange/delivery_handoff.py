"""Portable delivery intent and complete exact-case queue validation.

No local database, simulator, or physical acceptance is accessed here.
"""
import shlex
from pathlib import Path
from .common import read, sha, within

CHECKS = {'native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion'}
def validate_case(folder, entry, expected_sets=None):
    folder = Path(folder)
    case = entry['case_id']
    receipt = entry.get('delivery_acceptance')
    if not isinstance(receipt, dict) or receipt.get('case_id') != case:
        raise ValueError('Selected case lacks exact delivery acceptance contract: '+case)
    targets = set(expected_sets or ('demo-test', 'full-test'))
    if (not targets or not targets <= {'demo-train', 'full-train', 'demo-test', 'full-test', 'held-out'}
            or set(receipt.get('sets', [])) != targets
            or not CHECKS <= set(receipt.get('checks', []))):
        raise ValueError('Delivery acceptance omits a set or independent check: '+case)
    if (receipt.get('test_exit_code') != 0 or receipt.get('negative_exit_code') in (None, 0)
            or not receipt.get('negative_expected_error') or not receipt.get('command')
            or not receipt.get('negative_command') or not receipt.get('script')
            or not receipt.get('script_sha256') or not receipt.get('test_log')
            or not receipt.get('negative_log')):
        raise ValueError('Delivery acceptance lacks positive/negative CPU proof: '+case)
    if (sha(within(folder, receipt['script'])) != receipt['script_sha256']
            or sha(within(folder, receipt['test_log'])) != receipt.get('test_log_sha256')
            or sha(within(folder, receipt['negative_log'])) != receipt.get('negative_log_sha256')):
        raise ValueError('Delivery acceptance proof changed: '+case)
    if receipt['negative_expected_error'] not in within(folder, receipt['negative_log']).read_text():
        raise ValueError('Delivery negative proof did not show expected rejection: '+case)
    for name in ('command', 'negative_command'):
        try:
            tokens = shlex.split(receipt[name])
        except ValueError as error:
            raise ValueError('Malformed delivery acceptance command: '+case) from error
        if case not in tokens:
            raise ValueError('Delivery acceptance command selects another case: '+case)
    return receipt


def validate_queue(repo, assignments):
    repo = Path(repo)
    queue = read(repo / 'work/_shared/gpu-queue.json')
    if queue.get('format') != 'worker-ordered-gpu-queue-v1':
        raise ValueError('Wrong exact delivery queue format')
    expected_cases = set()
    expected_comparisons = set()
    for aid in assignments:
        folder = repo / 'work' / aid
        manifest = read(folder / 'execution-manifest.json')
        expected_cases.update((aid, item['case_id']) for item in manifest['cases'])
        plan = read(folder / 'case-plan.json')
        expected_comparisons.update((aid, item['comparison_id']) for item in plan['comparisons'])
    rows = queue.get('cases', [])
    actual = [(row.get('assignment_id'), row.get('case_id')) for row in rows]
    if (len(actual) != len(set(actual)) or set(actual) != expected_cases
            or [row.get('order') for row in rows] != list(range(1, len(rows)+1))):
        raise ValueError('Delivery queue does not cover every exact case once')
    for row in rows:
        for key in ('capture_command', 'postprocessing_command', 'owner_release_command',
                    'additional_source_audit_command'):
            if not row.get(key) or row['case_id'] not in row[key]:
                raise ValueError('Incomplete exact delivery queue command: '+row['case_id'])
        if read(repo / 'batch.json').get('canonical_delivery_queue_required'):
            for key, command in (('prepare_command', 'prepare-delivery'),
                                 ('execute_command', 'execute-delivery'),
                                 ('accept_command', 'accept-delivery')):
                value = row.get(key, '')
                if command not in value or row['case_id'] not in value:
                    raise ValueError('Missing canonical '+key+': '+row['case_id'])
            entry = next(item for item in read(repo/'work'/row['assignment_id']/'execution-manifest.json')['cases']
                         if item['case_id'] == row['case_id'])
            candidate_commands = row.get('candidate_commands')
            if not isinstance(candidate_commands, dict) or set(candidate_commands) != {
                    item['id'] for item in entry.get('candidates', [])}:
                raise ValueError('Queue does not cover exact fallback candidates: '+row['case_id'])
            for candidate_id, command in candidate_commands.items():
                if (candidate_id not in command or row['case_id'] not in command
                        or 'prepare-delivery' not in command):
                    raise ValueError('Fallback lacks canonical preparation command: '+row['case_id'])
    comparisons = queue.get('comparison_audit_commands', [])
    actual_comparisons = [(row.get('assignment_id'), row.get('comparison_id')) for row in comparisons]
    if (len(actual_comparisons) != len(set(actual_comparisons))
            or set(actual_comparisons) != expected_comparisons
            or any(not row.get('command') for row in comparisons)):
        raise ValueError('Delivery queue omits a comparison audit')
    if read(repo / 'batch.json').get('canonical_delivery_queue_required'):
        proof_path = repo/'work/_shared/local-integration-proof.json'
        proof = read(proof_path)
        needed = {'primary_job', 'fallback_job', 'saved_processing', 'rejected_audit'}
        target_set = read(repo/'batch.json').get('target_set')
        needed.add('accepted_targets' if target_set in ('demo-train', 'full-train', 'held-out')
                   else 'accepted_both_sets')
        if (proof.get('format') != 'worker-local-integration-proof-v1'
                or proof.get('passed') is not True
                or not needed <= set(proof.get('scenarios', []))
                or proof.get('exit_code') != 0
                or not proof.get('command')
                or sha(within(repo, proof.get('log', ''))) != proof.get('log_sha256')):
            raise ValueError('Missing tested canonical delivery integration proof')
    return {'cases': len(rows), 'comparisons': len(comparisons),
            'queue_sha256': sha(repo / 'work/_shared/gpu-queue.json')}
