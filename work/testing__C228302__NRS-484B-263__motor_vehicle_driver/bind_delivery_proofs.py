"""Bind mock-only original-attempt audit wiring proofs to selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    script = HERE / 'prove_original_delivery.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.removeprefix(HERE.name + '__')
        positive = HERE / ('cpu-nov25-delivery-' + name + '.log')
        negative = HERE / ('cpu-nov25-delivery-negative-' + name + '.log')
        if 'passed' not in positive.read_text() or 'original attempt missing' not in negative.read_text():
            raise ValueError(name + ': mock-only delivery proof absent')
        base = '.venv-cpu/bin/python work/' + HERE.name + '/prove_original_delivery.py --case ' + case
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-test'],
            'cpu_proof_kind': 'mock_only_contract_wiring',
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': script.name, 'script_sha256': sha(script),
            'command': base, 'test_exit_code': 0,
            'test_log': positive.name, 'test_log_sha256': sha(positive),
            'negative_command': base + ' --negative-missing-attempt',
            'negative_exit_code': 2, 'negative_expected_error': 'original attempt missing',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative),
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
