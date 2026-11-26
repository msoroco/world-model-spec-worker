"""Bind current CPU audit tests and exact missing-original-source rejection."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c150116-new'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    return '\n'.join(line.rstrip() for line in value.splitlines()).rstrip() + '\n'


def main():
    test_log = HERE / 'cpu-nov26-full-tests.log'
    if not test_log.is_file() or not test_log.read_text().rstrip().endswith('OK'):
        raise ValueError('current positive CPU audit suite missing')
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    script = HERE / 'delivery_audit.py'
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['TMPDIR'] = str(SCRATCH / 'tmp')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH / 'pipeline-delivery-negative')
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.removeprefix(HERE.name + '__')
        missing = SCRATCH / ('missing-original-' + name)
        output = SCRATCH / ('missing-original-' + name + '-audit.json')
        command = [sys.executable, str(script), 'case', '--attempt', str(missing),
                   '--case', case, '--output', str(output)]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        negative = HERE / ('cpu-nov26-original-negative-' + name + '.log')
        negative.write_text(clean(result.stdout + result.stderr))
        if result.returncode == 0 or 'original attempt missing' not in negative.read_text():
            raise ValueError(name + ': original missing-source rejection failed')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-test'], 'checks': CHECKS,
            'command': f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py case --attempt $ORIGINAL_ATTEMPT --case {case} --output $AUDIT_OUTPUT',
            'negative_command': f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py case --attempt {missing} --case {case} --output {output}',
            'script': script.name, 'script_sha256': sha(script),
            'test_exit_code': 0, 'test_log': test_log.name, 'test_log_sha256': sha(test_log),
            'negative_exit_code': result.returncode, 'negative_expected_error': 'original attempt missing',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative),
            'scope': 'CPU source-hashed audit implementation tests; original capture and physical completion pending'}
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
