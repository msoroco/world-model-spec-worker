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
        suffix = f'probe_0{index}'
        case = entry['case_id']
        physical = HERE / 'cases' / suffix / 'physical-preparation.json'
        if json.loads(physical.read_text())['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Physical preparation proof differs from exact selected construction')
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                         'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        positive = HERE / f'delivery-{suffix}-primary-positive.log'
        negative = HERE / f'delivery-{suffix}-negative.log'
        if ('"passed": true' not in positive.read_text() or
                'Missing source: device-original.jsonl' not in negative.read_text()):
            raise ValueError('Exact delivery CPU positive/negative tests differ')
        attempt = f'.runtime-work/c109166-public-v2-{suffix}-primary'
        process = f'work/{BASE}/saved-{suffix}-primary.log'
        if index == 1:
            negative_attempt = attempt
            negative_process = '.runtime-work/c109166-negative-device-processing.json'
            negative_output = '.runtime-work/c109166-delivery-v2-negative.json'
        else:
            negative_attempt = attempt
            negative_process = '.runtime-work/c109166-negative-device-processing-probe_02.json'
            negative_output = '.runtime-work/c109166-delivery-v2-negative-probe_02.json'
        prefix = f'.venv-cpu/bin/python work/{BASE}/delivery_audit.py --case {case} --candidate primary'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion',
                       'source_hashed_exception_applicability_review'],
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': (prefix + f' --attempt {attempt} --processing {process}' +
                        f' --output .runtime-work/c109166-delivery-v2-positive-{suffix}-primary.json --diagnostic'),
            'test_exit_code': 0, 'test_log': positive.name,
            'test_log_sha256': sha(positive),
            'negative_command': (prefix + f' --attempt {negative_attempt}' +
                                 f' --processing {negative_process}' +
                                 f' --output {negative_output} --diagnostic'),
            'negative_exit_code': 1,
            'negative_expected_error': 'Missing source: device-original.jsonl',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
        entry['post_capture'] = {
            'command': (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{BASE}/execution-manifest.json'
                        f' --case {case} --attempt "$ATTEMPT" --output "$OUTPUT"'
                        ' --library runtime/library --validator "$ADAPTER_CHECK"'),
            'feedback_command': f'.venv-cpu/bin/python runtime.py feedback --case {case} --attempt "$ATTEMPT"',
            'recorded_only': True,
            'test_exit_code': 0, 'test_log': f'saved-{suffix}-primary.log',
            'test_log_sha256': sha(HERE / f'saved-{suffix}-primary.log')}
    manifest['status'] = 'cpu_proofs_bound_source_review_pending'
    manifest['delivery_ready'] = False
    manifest['original_native_observed'] = False
    manifest['comparison_proof'] = {'path': 'comparison-proof.json',
                                    'sha256': sha(HERE / 'comparison-proof.json')}
    manifest['exception_review_cpu_proof'] = {'path': 'exception-review-proof.json',
                                              'sha256': sha(HERE / 'exception-review-proof.json')}
    write(manifest_path, manifest)
    print(json.dumps({'bound_cases': 2, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
