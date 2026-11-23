"""Bind stable exact-case CPU audit contracts into the selected manifest."""
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
AUDITOR = PACKAGE / 'native/delivery_audit.py'
EXPECTED = 'Original actor/frame/trace join differs at 599'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from worker_exchange.delivery_handoff import validate_case
    path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    proof_path = PACKAGE / 'native-audit-v2-proof.json'
    proof = json.loads(proof_path.read_text())
    if (proof['auditor_sha256'] != sha(AUDITOR)
            or proof['positive_count'] != 12
            or proof['join_rejections'] != 12
            or proof['synthetic_provenance_rejections'] != 12):
        raise ValueError('Production-capable source auditor CPU proof changed')
    proofs = {(item['case_id'], item['candidate']): item
              for item in proof['selected_chains']}
    for entry in manifest['cases']:
        case = entry['case_id']
        item = proofs[(case, 'primary')]
        positive_record, negative_record = item['positive'], item['reject_join']
        positive, negative = (PACKAGE / positive_record['log'],
                              PACKAGE / negative_record['log'])
        if (positive_record['exit_code'] != 0 or negative_record['exit_code'] == 0
                or positive_record['sha256'] != sha(positive)
                or negative_record['sha256'] != sha(negative)
                or EXPECTED not in negative.read_text()):
            raise ValueError('Exact-case CPU source audit changed: ' + case)
        command = positive_record['command']
        relative = lambda p: str(p.relative_to(PACKAGE))
        receipt = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels',
                       'physical_completion'],
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': EXPECTED,
            'command': command,
            'negative_command': negative_record['command'],
            'production_command': ' '.join((
                '.venv-cpu/bin/python',
                'work/' + PACKAGE.name + '/native/delivery_audit.py',
                '--case', case, '--candidate', '"${CANDIDATE_ID:-primary}"',
                '--attempt', '"$ATTEMPT_DIR"', '--saved', '"$SAVED_RECEIPT"')),
            'script': relative(AUDITOR), 'script_sha256': sha(AUDITOR),
            'test_log': relative(positive), 'test_log_sha256': sha(positive),
            'negative_log': relative(negative), 'negative_log_sha256': sha(negative),
        }
        validate_case(PACKAGE, {'case_id': case,
                                'delivery_acceptance': receipt}, ['full-train'])
        entry['delivery_acceptance'] = receipt
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    from worker_exchange.execution_manifest import validate
    validate(REPO, PACKAGE.name)
    for entry in manifest['cases']:
        validate_case(PACKAGE, entry, ['full-train'])
    print(json.dumps({'cases_bound': len(manifest['cases']),
                      'manifest_sha256': sha(path),
                      'native_execution_claimed': False}))


if __name__ == '__main__':
    main()
