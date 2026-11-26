"""Bind mock-only independent delivery and comparison CPU proof receipts."""
import hashlib
import json
from pathlib import Path

from package_spec import CASES, HERE, ROOT, case_id


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    script = HERE / 'prove_original_delivery.py'
    python = ROOT / '.venv-cpu/bin/python'
    for entry in manifest['cases']:
        cid = entry['case_id']
        name = cid.removeprefix(HERE.name + '__')
        positive = HERE / ('cpu-delivery-positive-' + name + '.log')
        negative = HERE / ('cpu-delivery-negative-' + name + '.log')
        if ('"source_complete_wiring": true' not in positive.read_text() or
                'original reviewed bus site packet missing' not in negative.read_text()):
            raise ValueError('independent delivery CPU proof missing: ' + name)
        base = f'{python} {script} --case {cid}'
        entry['delivery_acceptance'] = {
            'case_id': cid, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'cpu_proof_kind': 'mock_only_contract_wiring',
            'script': script.name, 'script_sha256': sha(script),
            'command': base, 'test_exit_code': 0,
            'test_log': positive.name, 'test_log_sha256': sha(positive),
            'negative_command': base + ' --negative-missing-review',
            'negative_exit_code': 2,
            'negative_expected_error': 'original reviewed bus site packet missing',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('bound independent mock-only delivery receipts:', len(manifest['cases']))


if __name__ == '__main__':
    main()
