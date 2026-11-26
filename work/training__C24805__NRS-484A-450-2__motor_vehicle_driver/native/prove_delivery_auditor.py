"""Exercise the independent original-source delivery rejection boundary."""

import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SCRIPT = HERE / 'delivery_audit.py'
SCRATCH = ROOT / '.runtime-work/c24805-selected'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_log(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(line.rstrip() for line in
                              value.rstrip().splitlines()) + '\n')


def main():
    records = []
    for suffix in ('probe_a', 'probe_b'):
        case = HERE.name + '__' + suffix
        command = [str(ROOT / '.venv-cpu/bin/python'), str(SCRIPT),
                   '--case', case, '--selftest']
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output'),
                   TMPDIR=str(SCRATCH), PYTHONPATH='runtime/scenario_pipeline',
                   PYTHONDONTWRITEBYTECODE='1')
        positive = subprocess.run(command, cwd=ROOT, env=env,
                                  capture_output=True, text=True, check=False)
        negative = subprocess.run(command + ['--negative-fixture'], cwd=ROOT,
                                  env=env, capture_output=True, text=True, check=False)
        base = HERE / 'delivery-acceptance' / suffix
        positive_log, negative_log = base / 'positive.log', base / 'negative.log'
        write_log(positive_log, positive.stdout + positive.stderr)
        write_log(negative_log, negative.stdout + negative.stderr)
        expected = 'Synthetic fixture cannot establish original Native delivery'
        if positive.returncode or negative.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError(f'Independent delivery selftest failed: {case}')
        records.append({'case_id': case, 'checks': ['native_source',
                          'all_participants', 'time_join', 'full_video_decode',
                          'actual_pixels', 'physical_completion'],
                        'script': SCRIPT.relative_to(HERE).as_posix(),
                        'script_sha256': sha(SCRIPT),
                        'command': ' '.join(command), 'test_exit_code': positive.returncode,
                        'test_log': positive_log.relative_to(HERE).as_posix(),
                        'test_log_sha256': sha(positive_log),
                        'negative_command': ' '.join(command + ['--negative-fixture']),
                        'negative_exit_code': negative.returncode,
                        'negative_expected_error': expected,
                        'negative_log': negative_log.relative_to(HERE).as_posix(),
                        'negative_log_sha256': sha(negative_log)})
    target = HERE / 'delivery-audit-proofs.json'
    target.write_text(json.dumps({'format': 'c24805-delivery-audit-proofs-v1',
                                  'proofs': records}, indent=2) + '\n')
    print(json.dumps({'proof_count': len(records), 'sha256': sha(target)},
                     sort_keys=True))


if __name__ == '__main__':
    main()
