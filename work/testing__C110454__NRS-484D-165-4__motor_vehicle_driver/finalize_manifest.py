"""Bind one immutable selected parked-headlamp CPU proof revision."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SCRATCH = '.runtime-work/c110454-owner'
VALIDATOR = '.runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    manifest['status'] = 'selected_cpu_prepared'
    for entry in manifest['cases']:
        case = entry['case_id']
        mode = case.rsplit('__', 1)[1]
        base = f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/execution-manifest.draft.json --case {case}'
        log = f'cpu-offline-{mode}-primary.log'
        entry['offline'] = {'construction_sha256': entry['construction_sha256'],
                            'command': base + f' --output {SCRATCH}/offline-{mode}-primary-rev3 --python "$PWD/.venv-cpu/bin/python"',
                            'exit_code': 0, 'log': log, 'log_sha256': sha(HERE / log)}
        receipt = f'compat-{mode}-receipt.json'
        entry['compatibility'] = {'receipt': receipt, 'sha256': sha(HERE / receipt),
                                  'log': f'compat-{mode}-analysis.log'}
        entry['negative'] = {'log': f'compat-{mode}-negative.log'}
        entry['physical_preparation'] = {'receipt': f'physical-preparation-{mode}.json',
            'sha256': sha(HERE / f'physical-preparation-{mode}.json')}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        post_command = (f'.venv-cpu/bin/python runtime.py process-saved --manifest '
            f'work/{ASSIGNMENT}/execution-manifest.draft.json --case {case} '
            f'--attempt ORIGINAL_ATTEMPT --output {SCRATCH}/saved-process-{mode} '
            f'--library runtime/library --validator {VALIDATOR} '
            '--owner-release-receipt ORIGINAL_OWNER_RELEASE_RECEIPT')
        post_log = f'cpu-process-saved-{mode}.log'
        entry['post_capture'] = {'recorded_only': True, 'command': post_command,
            'feedback_command': f'cat {SCRATCH}/saved-process-{mode}/v0001/processing.json',
            'test_exit_code': 0, 'test_log': post_log,
            'test_log_sha256': sha(HERE / post_log)}
        script = 'selected_delivery_audit.py'
        command = (f'.venv-cpu/bin/python work/{ASSIGNMENT}/{script} --case {case} '
                   f'--attempt {SCRATCH}/compat-{mode}-primary-rev3 '
                   f'--output work/{ASSIGNMENT}/delivery-diagnostic-{mode}.json '
                   '--diagnostic-fixture')
        negative_source = 'site-packet.json' if mode == 'unlit' else 'lamp-roi.json'
        negative_command = (f'.venv-cpu/bin/python work/{ASSIGNMENT}/{script} --case {case} '
                   f'--attempt {SCRATCH}/compat-{mode}-primary-rev3 '
                   f'--output {SCRATCH}/negative-{mode}.json --diagnostic-fixture '
                   f'--negative-remove-source {negative_source}')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-test'], 'checks': CHECKS,
            'script': script, 'script_sha256': sha(HERE / script),
            'command': command, 'test_exit_code': 0,
            'test_log': f'delivery-diagnostic-{mode}.log',
            'test_log_sha256': sha(HERE / f'delivery-diagnostic-{mode}.log'),
            'negative_command': negative_command, 'negative_exit_code': 1,
            'negative_expected_error': 'Missing required source: ' + negative_source,
            'negative_log': f'delivery-negative-{mode}.log',
            'negative_log_sha256': sha(HERE / f'delivery-negative-{mode}.log')}
        candidate = entry['candidates'][0]
        log = f'cpu-offline-{mode}-fallback1.log'
        candidate['offline'] = {'construction_sha256': candidate['construction_sha256'],
            'command': base + f' --candidate fallback1 --output {SCRATCH}/offline-{mode}-fallback1-rev3 --python "$PWD/.venv-cpu/bin/python"',
            'exit_code': 0, 'log': log, 'log_sha256': sha(HERE / log)}
        receipt = f'fallback1-compat-{mode}-receipt.json'
        candidate['compatibility'] = {'receipt': receipt, 'sha256': sha(HERE / receipt),
            'log': f'fallback1-compat-{mode}-analysis.log',
            'negative_log': f'fallback1-compat-{mode}-negative.log'}
    (HERE / 'execution-manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('bound', len(manifest['cases']), 'selected cases to exact CPU proofs')


if __name__ == '__main__':
    main()
