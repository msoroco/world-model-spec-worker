"""Attach exact case delivery audit and current offline CPU receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    script = 'prove_delivery_audit.py'
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        base = ('.runtime-work/c110264-output/compat-left_signal-v2' if suffix == 'left_signal'
                else f'.runtime-work/c110264-output/compat-{suffix}-primary-v2')
        cmd = f'.venv-cpu/bin/python work/{HERE.name}/{script} --case {case_id} --attempt {base}'
        positive = f'cpu-delivery-{suffix}-positive.log'
        negative = f'cpu-delivery-{suffix}-negative.log'
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'scope': 'Synthetic diagnostic source audit; original Native pixels and physical review pending',
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'command': cmd + ' --mode positive', 'test_exit_code': 0,
            'test_log': positive, 'test_log_sha256': digest(HERE / positive),
            'negative_command': cmd + ' --mode negative', 'negative_exit_code': 1,
            'negative_expected_error': 'Missing required source: original-attempt/native/trace.json',
            'negative_log': negative, 'negative_log_sha256': digest(HERE / negative),
            'script': script, 'script_sha256': digest(HERE / script),
        }
        for candidate_id, selected in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            offline = selected['offline']
            offline['command'] = offline['command'].replace('offline7-', 'offline8-')
            offline['log_sha256'] = digest(HERE / offline['log'])
        entry['post_capture'] = {
            'recorded_only': True,
            'command': (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved '
                        f'--manifest work/{HERE.name}/execution-manifest.json --case {case_id} '
                        '--attempt "$ATTEMPT" --output "$SAVED_OUTPUT" '
                        '--library "$LIBRARY" --validator "$VALIDATOR" '
                        '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'feedback_command': (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved '
                                 f'--manifest work/{HERE.name}/execution-manifest.json --case {case_id} '
                                 '--attempt "$ATTEMPT" --output "$SAVED_OUTPUT" '
                                 '--library "$LIBRARY" --validator "$VALIDATOR" '
                                 '--owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'proof_scope': 'source-shaped synthetic diagnostic; original Native capture and owner release pending',
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
