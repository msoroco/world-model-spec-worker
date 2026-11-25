"""Bind tested original-source audit commands to the selected manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PYTHON = REPO / '.venv-cpu/bin/python'
RUNTIME = REPO / 'runtime.py'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'
SCRATCH = REPO / '.runtime-work/c111329-original-audit-proof'
SELECTED = REPO / '.runtime-work/c111329-2871d-selected'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args) -> str:
    return ' '.join(str(arg) for arg in args)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        saved = HERE / f'cpu-sealed-{suffix}-saved.log'
        post = command(PYTHON, RUNTIME, 'process-saved', '--manifest', MANIFEST,
                       '--case', case, '--attempt', SELECTED / f'{suffix}-sealed-compat',
                       '--output', SELECTED / f'{suffix}-sealed-saved',
                       '--library', REPO / 'runtime/library', '--validator', VALIDATOR)
        entry['post_capture'] = {
            'recorded_only': True, 'command': post, 'feedback_command': post,
            'test_exit_code': 0, 'test_log': saved.name,
            'test_log_sha256': sha(saved),
        }
        entry['negative'] = {'log': f'cases/{suffix}/primary-negative-analysis.log'}
        entry['acquisition'] = {
            'walker_center_xy': {
                'entrypoint': 'native_acquisition.py',
                'method': 'original walker center and body pose on each synchronous tick',
                'evidence': 'Native rows, trace and capture/evidence frame joins',
            },
            'device_readback': {
                'entrypoint': 'native_acquisition.py',
                'method': 'source-bound official pedestrian device state on each synchronous tick',
                'evidence': 'reviewed device survey and sealed Native rows',
            },
            'camera_frame_map': {
                'entrypoint': 'capture_export.py',
                'method': 'four original camera frame identities and PNG hashes',
                'evidence': 'Native camera hashes, video_frames.jsonl and four FFV1 streams',
            },
        }
        root = SCRATCH / suffix
        script = HERE / 'original_attempt_audit.py'
        base = command(PYTHON, script, '--case', case, '--attempt', root,
                       '--refs', root / 'source-refs.json')
        positive = HERE / f'cpu-original-audit-{suffix}-positive.log'
        negative = HERE / f'cpu-original-audit-{suffix}-negative.log'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': script.name, 'script_sha256': sha(script),
            'command': base + command(' --output', HERE / 'cases' / suffix / 'original-audit-diagnostic.json',
                                        '--allow-diagnostic', '--expected-frames', 3),
            'test_exit_code': 0, 'test_log': positive.name,
            'test_log_sha256': sha(positive),
            'negative_command': base + command(' --output', SCRATCH / (suffix + '-negative.json')),
            'negative_exit_code': 1, 'negative_expected_error': 'unreviewed original site rejected',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative),
            'production_source_audit_command':
                command(PYTHON, script, '--case', case, '--attempt', '"$ATTEMPT"',
                        '--refs', '"$ATTEMPT/source-refs.json"', '--output', '"$AUDIT_REPORT"'),
            'scope': 'CPU diagnostic proof; original physical and legal reviews remain pending',
        }
    script = HERE / 'original_comparison_audit.py'
    comparisons = []
    for spec in json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))['comparisons']:
        label = spec['comparison_id']
        positive = HERE / f'cpu-original-comparison-{label}-positive.log'
        negative = HERE / f'cpu-original-comparison-{label}-negative.log'
        receipt = HERE / 'comparisons' / (label + '.original-diagnostic.json')
        comparisons.append({
            'comparison_id': label, 'case_ids': spec['case_ids'],
            'command': command(PYTHON, script, '--comparison', label,
                               '--first-attempt', '"$FIRST_ATTEMPT"',
                               '--first-refs', '"$FIRST_ATTEMPT/source-refs.json"',
                               '--second-attempt', '"$SECOND_ATTEMPT"',
                               '--second-refs', '"$SECOND_ATTEMPT/source-refs.json"',
                               '--output', '"$COMPARISON_REPORT"'),
            'script_sha256': sha(script),
            'fixed_conditions': spec['fixed_conditions'],
            'deliberate_differences': spec['deliberate_differences'],
            'diagnostic_cli_proof': {'receipt': str(receipt.relative_to(HERE)),
                                     'receipt_sha256': sha(receipt),
                                     'positive_log': positive.name,
                                     'positive_log_sha256': sha(positive),
                                     'negative_log': negative.name,
                                     'negative_log_sha256': sha(negative)},
        })
    manifest['original_comparison_audits'] = comparisons
    manifest['source_audit_protocol'].update({
        'source_refs_command': command(PYTHON, HERE / 'seal_original_refs.py',
                                       '--attempt', '"$ATTEMPT"',
                                       '--output', '"$ATTEMPT/source-refs.json"'),
        'production_audit_script': 'original_attempt_audit.py',
        'production_audit_script_sha256': sha(HERE / 'original_attempt_audit.py'),
        'source_review_command': 'reviewed_site.verify against original map and pedestrian device packets',
        'pinned_profile': '900 original frames, 20 Hz, four source-hashed FFV1 videos and PNG streams',
    })
    manifest['comparison_audit_protocol'].update({
        'production_audit_script': script.name,
        'production_audit_script_sha256': sha(script),
        'comparison_ids': [row['comparison_id'] for row in comparisons],
    })
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('manifest sha256', sha(MANIFEST))


if __name__ == '__main__':
    main()
