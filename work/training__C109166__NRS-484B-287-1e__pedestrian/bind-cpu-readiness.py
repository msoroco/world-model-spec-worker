"""Bind reviewed-source-gated CPU physical and delivery diagnostic receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    script = HERE / 'delivery_audit.py'
    for index, entry in enumerate(manifest['cases'], 1):
        suffix = f'controlled_{index}'
        case = entry['case_id']
        physical = HERE / 'cases' / suffix / 'physical-preparation.json'
        if json.loads(physical.read_text())['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Physical preparation proof differs from exact selected construction')
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                         'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        positive = HERE / f'delivery-{index}-positive.log'
        negative = HERE / f'delivery-{index}-negative.log'
        if ('"passed": true' not in positive.read_text() or
                'Missing source: device-original.jsonl' not in negative.read_text()):
            raise ValueError('Exact delivery CPU positive/negative tests differ')
        attempt = f'.runtime-work/c109166-public-r5-{suffix}-primary'
        process = f'work/{BASE}/saved-{index}-primary.log'
        if index == 1:
            negative_attempt = '.runtime-work/c109166-saved-r5-negative-source'
            negative_process = f'work/{BASE}/saved-1-negative.log'
            negative_output = '.runtime-work/c109166-delivery-diagnostic-negative.json'
        else:
            negative_attempt = attempt
            negative_process = '.runtime-work/c109166-delivery-negative-2-processing.json'
            negative_output = '.runtime-work/c109166-delivery-diagnostic-negative-2.json'
        prefix = f'.venv-cpu/bin/python work/{BASE}/delivery_audit.py --case {case} --candidate primary'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': (prefix + f' --attempt {attempt} --processing {process}' +
                        f' --output .runtime-work/c109166-delivery-diagnostic-{index}.json --diagnostic'),
            'test_exit_code': 0, 'test_log': positive.name,
            'test_log_sha256': sha(positive),
            'negative_command': (prefix + f' --attempt {negative_attempt}' +
                                 f' --processing {negative_process}' +
                                 f' --output {negative_output} --diagnostic'),
            'negative_exit_code': 1,
            'negative_expected_error': 'Missing source: device-original.jsonl',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
    manifest['status'] = 'cpu_proofs_bound_source_review_pending'
    manifest['delivery_ready'] = False
    manifest['original_native_observed'] = False
    manifest['comparison_proof'] = {'path': 'comparison-proof.json',
                                    'sha256': sha(HERE / 'comparison-proof.json')}
    write(manifest_path, manifest)
    print(json.dumps({'bound_cases': 2, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
