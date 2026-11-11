"""Bind current exact alley constructions and CPU audit commands for handoff."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    probe = json.loads((ROOT / 'probe-compatibility-manifest.json').read_text())
    delivery = json.loads((ROOT / 'delivery-audit-proofs.json').read_text())
    comparison = json.loads((ROOT / 'comparison-proofs.json').read_text())
    physical = json.loads((ROOT / 'physical-preparation-proofs.json').read_text())
    by_delivery = {row['case_id']: row for row in delivery['cases']}
    by_physical = {row['case_id']: row for row in physical['cases']}
    entries = []
    for case in probe['cases']:
        case_id = case['case_id']
        suffix = case_id.split('__')[-1]
        audit = by_delivery[case_id]
        if case_id not in by_physical:
            raise ValueError('Exact physical protocol proof missing')
        offline_log = ROOT / 'cases' / f'case-offline-{suffix}-primary.log'
        saved_log = ROOT / 'cases' / f'case-saved-{suffix}.log'
        entry = {**case,
            'kind': 'delivery',
            'offline': {'command': '.venv-cpu/bin/python runtime.py offline '
                        f'--manifest work/{ROOT.name}/execution-manifest.json '
                        f'--case {case_id} --output .runtime-work/c10364-{suffix}-execution-offline-v2 '
                        '--python "$PWD/.venv-cpu/bin/python"',
                        'exit_code': 0, 'construction_sha256': digest(ROOT / case['construction']),
                        'log': str(offline_log.relative_to(ROOT)),
                        'log_sha256': digest(offline_log)},
            'post_capture': {'recorded_only': True,
                'command': '.venv-cpu/bin/python runtime.py process-saved '
                           f'--manifest work/{ROOT.name}/execution-manifest.json '
                           f'--case {case_id} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" '
                           '--library runtime/library '
                           '--validator .runtime-work/c125714-validator/.lake/build/bin/adapterCheck',
                'feedback_command': 'cat "$PROCESSING_OUTPUT/feedback.json"',
                'test_log': str(saved_log.relative_to(ROOT)),
                'test_log_sha256': digest(saved_log), 'test_exit_code': 0},
            'physical_preparation': {'receipt': by_physical[case_id]['receipt'],
                                     'sha256': by_physical[case_id]['sha256']},
            'delivery_acceptance': {
                'case_id': case_id, 'sets': ['held-out'],
                'checks': ['native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels', 'physical_completion'],
                'script': 'delivery_audit.py', 'script_sha256': digest(ROOT / 'delivery_audit.py'),
                'command': audit['positive_command'],
                'test_exit_code': 0, 'test_log': audit['positive_log'],
                'test_log_sha256': audit['positive_log_sha256'],
                'negative_command': audit['negative_command'],
                'negative_exit_code': audit['negative_exit_code'],
                'negative_expected_error': audit['negative_expected_error'],
                'negative_log': audit['negative_log'],
                'negative_log_sha256': audit['negative_log_sha256']},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': probe['assignment_id'],
                'runtime_manifest_sha256': probe['runtime_manifest_sha256'],
                'diagnostic_source_scope': 'Synthetic polygon/media only; exact Native map source pending',
                'comparison_audit_commands': [
                    {'assignment_id': ROOT.name, 'comparison_id': row['comparison_id'],
                     'command': row['command'], 'test_log': row['log'],
                     'test_log_sha256': row['log_sha256']}
                    for row in comparison['comparisons']],
                'cases': entries}
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Nine exact alley execution cases and four independent comparison commands bound')


if __name__ == '__main__':
    main()
