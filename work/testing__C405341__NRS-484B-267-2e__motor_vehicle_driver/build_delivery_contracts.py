"""Bind independent original audit implementation and missing-source rejection."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c405341'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    test_log = HERE / 'cpu-tests.log'
    if 'Ran 13 tests' not in test_log.read_text() or 'OK' not in test_log.read_text():
        raise ValueError('current independent audit CPU suite missing')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        name = case_id.removeprefix(HERE.name + '__')
        missing = SCRATCH / ('missing-original-' + name)
        missing_result = SCRATCH / ('missing-original-' + name + '-result.json')
        missing_output = SCRATCH / ('missing-original-' + name + '-audit.json')
        command = [sys.executable, str(HERE / 'delivery_audit.py'),
            '--attempt', str(missing), '--processed', str(missing_result),
            '--case', case_id, '--output', str(missing_output)]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output-root'),
                   TMPDIR=str(SCRATCH / 'tmp'), PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        if result.returncode != 1 or 'original attempt missing' not in result.stderr or missing_output.exists():
            raise ValueError('negative original delivery gate failed: ' + name)
        log = HERE / ('cpu-original-negative-' + name + '.log')
        log.write_text(result.stderr.rstrip() + '\n', encoding='utf-8')
        positive = ('.venv-cpu/bin/python work/' + HERE.name + '/delivery_audit.py'
            + ' --attempt $ORIGINAL_ATTEMPT --processed $PROCESSED_RESULT --case '
            + case_id + ' --output $AUDIT_OUTPUT')
        negative = ('.venv-cpu/bin/python work/' + HERE.name + '/delivery_audit.py'
            + ' --attempt ' + str(missing) + ' --processed ' + str(missing_result)
            + ' --case ' + case_id + ' --output ' + str(missing_output))
        entry['delivery_acceptance'] = {'case_id': case_id, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'command': positive, 'negative_command': negative,
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'test_exit_code': 0, 'test_log': test_log.name,
            'test_log_sha256': sha(test_log), 'negative_exit_code': 1,
            'negative_expected_error': 'original attempt missing',
            'negative_log': log.name, 'negative_log_sha256': sha(log),
            'scope': 'CPU audit implementation and missing-original rejection; original pixels and legal judgment pending'}
    path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
