"""Bind exact exposure constructions and CPU proofs for local Native handoff."""

import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parent
repo = root.parents[1]
primary = json.loads((root / 'probe-compatibility-manifest.json').read_text())
fallbacks = json.loads((root / 'fallback-constructions-manifest.json').read_text())
physical = json.loads((root / 'physical-preparation-proofs.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
by_fallback = {item['case_id']: item for item in fallbacks['cases']}
by_physical = {item['case_id']: item for item in physical['cases']}
entries = []
for case in primary['cases']:
    ident = case['case_id']
    suffix = ident.split('__')[-1]
    fallback = by_fallback[ident]
    proof = by_physical[ident]
    offline_log = f'cases/execution-offline-{suffix}.log'
    offline_command = (f'.venv-cpu/bin/python runtime.py offline --manifest work/{root.name}/execution-manifest.json '
                       f'--case {ident} --output .runtime-work/c136539-{suffix}-execution-offline-a '
                       f'--python "$PWD/.venv-cpu/bin/python"')
    saved_log = f'cases/execution-saved-{suffix}.log'
    positive = f'delivery-audit-{suffix if suffix != "slow_person_exposure" else "slow"}-positive.log'
    negative = f'delivery-audit-{suffix if suffix != "slow_person_exposure" else "slow"}-negative.log'
    entry = {**case,
             'kind': 'delivery',
             'candidate_risk': fallback['candidate_risk'],
             'candidates': fallback['candidates'],
             'offline': {'command': offline_command, 'exit_code': 0,
                         'construction_sha256': sha(root / case['construction']),
                         'log': offline_log, 'log_sha256': sha(root / offline_log)},
             'post_capture': {
                 'recorded_only': True,
                 'command': (f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{root.name}/execution-manifest.json '
                             f'--case {ident} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" '
                             f'--library runtime/library --validator .runtime-work/c125714-validator/.lake/build/bin/adapterCheck'),
                 'feedback_command': 'cat "$PROCESSING_OUTPUT/feedback.json"',
                 'test_log': saved_log, 'test_log_sha256': sha(root / saved_log), 'test_exit_code': 0},
             'physical_preparation': {'receipt': proof['receipt'], 'sha256': proof['sha256']},
             'delivery_acceptance': {
                 'case_id': ident, 'sets': ['held-out'],
                 'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                            'actual_pixels', 'physical_completion'],
                 'script': 'delivery_audit.py', 'script_sha256': sha(root / 'delivery_audit.py'),
                 'command': (f'.venv-cpu/bin/python work/{root.name}/delivery_audit.py --case {ident} '
                             f'--attempt .runtime-work/c136539-{suffix}-compat-passage-a '
                             f'--report .runtime-work/c136539-{suffix}-compat-passage-a/analysis-report.json '
                             '--diagnostic-fixture'),
                 'test_exit_code': 0, 'test_log': positive, 'test_log_sha256': sha(root / positive),
                 'negative_command': (f'.venv-cpu/bin/python work/{root.name}/delivery_audit.py --case {ident} '
                                      f'--attempt .runtime-work/c136539-{suffix}-compat-passage-a '
                                      f'--report .runtime-work/c136539-{suffix}-tampered-passage-report.json '
                                      '--diagnostic-fixture'),
                 'negative_exit_code': 1, 'negative_expected_error': 'hash differs',
                 'negative_log': negative, 'negative_log_sha256': sha(root / negative)},
             'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                                'port_env_var': 'CARLA_PORT'}}
    # The case's compatibility receipt is diagnostic; local Native acceptance
    # remains a separate sealed capture and independent audit.
    entries.append(entry)
manifest = {'format': 'worker-execution-manifest', 'assignment_id': primary['assignment_id'],
            'runtime_manifest_sha256': primary['runtime_manifest_sha256'], 'cases': entries}
(root / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
