"""Bind tested recorded-only processing commands to every selected case."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    index = json.loads((HERE / 'aggregate-saved/index.json').read_text())
    by_case = {item['case_id']: item for item in index['cases']}
    if set(by_case) != {entry['case_id'] for entry in manifest['cases']}:
        raise ValueError('Aggregate saved proof omits selected case')
    for entry in manifest['cases']:
        case = entry['case_id']
        proof = by_case[case]
        command = ('.venv-cpu/bin/python runtime.py process-saved '
                   f'--manifest work/{HERE.name}/execution-manifest.json '
                   f'--case {case} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" '
                   '--library runtime/library '
                   '--validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck')
        entry['post_capture'] = {'recorded_only': True, 'command': command,
            'feedback_command': 'cat "$PROCESSING_OUTPUT/feedback.json"',
            'test_log': proof['log'], 'test_log_sha256': proof['log_sha256'],
            'test_exit_code': 0}
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
