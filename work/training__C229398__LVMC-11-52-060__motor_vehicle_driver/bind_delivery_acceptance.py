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
    for entry in manifest['cases']:
        case = entry['case_id']
        group = case.rsplit('__', 1)[-1]
        feet = {'below_15_ft': '14ft', 'at_15_ft': '15ft',
                'above_15_ft': '16ft'}[group]
        attempt = REPO / '.runtime-work' / ('c229398-compat-' + feet + '-atoms-primary')
        saved = PACKAGE / 'diagnostic-fixture' / group / 'proofs/atoms-primary-saved.json'
        proof_dir = PACKAGE / 'diagnostic-fixture' / group / 'proofs'
        positive = proof_dir / 'independent-delivery-positive.log'
        negative = proof_dir / 'independent-delivery-negative.log'
        proof = json.loads((proof_dir / 'independent-delivery-proof.json').read_text())
        if (not attempt.is_dir() or not saved.is_file()
                or proof['case_id'] != case or proof['script_sha256'] != sha(AUDITOR)
                or proof['positive_log_sha256'] != sha(positive)
                or proof['negative_log_sha256'] != sha(negative)
                or proof['negative_error_contains'] != EXPECTED):
            raise ValueError('Existing exact-case source audit changed: ' + case)
        command = ' '.join((str(REPO / '.venv-cpu/bin/python'), str(AUDITOR),
                            '--case', case, '--attempt', str(attempt),
                            '--saved', str(saved)))
        relative = lambda p: str(p.relative_to(PACKAGE))
        receipt = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels',
                       'physical_completion'],
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': EXPECTED,
            'command': command,
            'negative_command': command + ' --reject-frame-join',
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
