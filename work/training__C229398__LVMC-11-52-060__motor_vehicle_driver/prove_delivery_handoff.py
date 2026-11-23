"""Run exact-case CPU handoff diagnostics and preserve source-hashed logs."""
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
AUDITOR = PACKAGE / 'audit_delivery_handoff.py'
EXPECTED = 'Source join differs:'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_id, negative):
    suffix = case_id.rsplit('__', 1)[-1]
    command = [sys.executable, str(AUDITOR), '--case', case_id]
    if negative:
        command.append('--corrupt-final-join')
    completed = subprocess.run(command, cwd=REPO, capture_output=True,
                               text=True, timeout=300)
    name = 'delivery-handoff-' + suffix + ('-negative' if negative else '-positive') + '.log'
    log = PACKAGE / name
    log.write_text(completed.stdout + completed.stderr)
    if negative:
        if completed.returncode == 0 or EXPECTED not in log.read_text():
            raise ValueError('Corrupt exact-case source join was not rejected: ' + case_id)
    else:
        if completed.returncode != 0:
            raise ValueError('Exact-case source diagnostic failed: ' + case_id)
        payload = json.loads(completed.stdout)
        if (payload['case_id'] != case_id or payload['candidate_count'] != 4
                or payload['accepted'] is not False
                or payload['source_kind'] != 'synthetic_native_sample'):
            raise ValueError('Exact-case diagnostic falsely accepted source')
    return {'command': ' '.join(command), 'exit_code': completed.returncode,
            'log': name, 'log_sha256': sha(log)}


def main():
    from worker_exchange.delivery_handoff import validate_case
    manifest = PACKAGE / 'execution-manifest.json'
    data = json.loads(manifest.read_text())
    records = []
    for case in data['cases']:
        case_id = case['case_id']
        positive = run(case_id, False)
        negative = run(case_id, True)
        contract = {
            'case_id': case_id, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels',
                       'physical_completion'],
            'test_exit_code': positive['exit_code'],
            'negative_exit_code': negative['exit_code'],
            'negative_expected_error': EXPECTED,
            'command': positive['command'],
            'negative_command': negative['command'],
            'script': 'audit_delivery_handoff.py',
            'script_sha256': sha(AUDITOR),
            'test_log': positive['log'],
            'test_log_sha256': positive['log_sha256'],
            'negative_log': negative['log'],
            'negative_log_sha256': negative['log_sha256'],
        }
        validate_case(PACKAGE, {'case_id': case_id,
                                'delivery_acceptance': contract}, ['full-train'])
        tampered = deepcopy(contract)
        tampered['script_sha256'] = '0' * 64
        try:
            validate_case(PACKAGE, {'case_id': case_id,
                                    'delivery_acceptance': tampered}, ['full-train'])
        except ValueError as error:
            if 'proof changed' not in str(error):
                raise
        else:
            raise ValueError('Pinned handoff accepted a changed script hash')
        records.append({'case_id': case_id, 'positive': positive,
                        'negative': negative, 'delivery_acceptance': contract,
                        'pinned_handoff_validation_passed': True,
                        'tampered_script_hash_rejected': True,
                        'negative_expected_error': EXPECTED,
                        'script': 'audit_delivery_handoff.py',
                        'script_sha256': sha(AUDITOR),
                        'checks': ['native_source', 'all_participants', 'time_join',
                                   'full_video_decode', 'actual_pixels',
                                   'physical_completion'],
                        'accepted': False, 'original_native_verified': False,
                        'actual_pixels_verified': False,
                        'physical_completion_verified': False})
    proof = {'format': 'c229398-exact-case-delivery-handoff-cpu-v1',
             'assignment_id': PACKAGE.name,
             'execution_manifest_sha256': sha(manifest),
             'cases': records, 'positive_count': len(records),
             'negative_rejection_count': len(records),
             'diagnostic_only': True, 'delivery_ready': False}
    path = PACKAGE / 'delivery-handoff-cpu.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'cases': len(records), 'proof_sha256': sha(path),
                      'delivery_ready': False}))


if __name__ == '__main__':
    main()
