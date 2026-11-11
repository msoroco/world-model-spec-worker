"""Bind positive and stale-source negative CPU acceptance fixtures per case."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
manifest = json.loads(MANIFEST.read_text())
logs = HERE / 'acceptance'
logs.mkdir(exist_ok=True)
script = HERE / 'acceptance_fixture.py'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


for entry in manifest['cases']:
    case = entry['case_id']
    stem = case.split('__')[-1]
    outcomes = {}
    for negative in (False, True):
        key = 'negative' if negative else 'positive'
        command = [sys.executable, str(script), '--case', case]
        if negative:
            command.append('--negative')
        process = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
        log = logs / f'{stem}-{key}.log'
        log.write_text(process.stdout)
        if (negative and (process.returncode == 0 or 'stale' not in process.stdout)) or (
                not negative and process.returncode != 0):
            raise ValueError(f'{stem} {key} failed: {process.stdout[-1000:]}')
        outcomes[key] = process, log
    positive, negative = outcomes['positive'], outcomes['negative']
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['held-out'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'command': f'.venv-cpu/bin/python work/{HERE.name}/acceptance_fixture.py --case {case}',
        'test_exit_code': 0, 'test_log': str(positive[1].relative_to(HERE)),
        'test_log_sha256': digest(positive[1]),
        'negative_command': f'.venv-cpu/bin/python work/{HERE.name}/acceptance_fixture.py --case {case} --negative',
        'negative_exit_code': negative[0].returncode,
        'negative_expected_error': 'stale',
        'negative_log': str(negative[1].relative_to(HERE)),
        'negative_log_sha256': digest(negative[1]),
        'script': script.name, 'script_sha256': digest(script),
        'fixture_only': True}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Bound exact synthetic acceptance tests for', len(manifest['cases']), 'cases')
