"""Run and bind exact-case CPU acceptance fixtures, including stale-source rejection."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
manifest_path = folder / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
logs = folder / 'acceptance'
logs.mkdir(exist_ok=True)
script = folder / 'acceptance_fixture.py'
script_sha = hashlib.sha256(script.read_bytes()).hexdigest()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    case = entry['case_id']
    stem = case.split('__')[-1]
    commands = {}
    for negative in (False, True):
        key = 'negative' if negative else 'positive'
        command = [str(repo / '.venv-cpu/bin/python'), str(script), '--case', case]
        if negative:
            command.append('--negative')
        outcome = subprocess.run(command, cwd=repo, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, check=False)
        log = logs / f'{stem}-{key}.log'
        log.write_text(outcome.stdout)
        if (negative and (outcome.returncode == 0 or 'stale' not in outcome.stdout)) or (not negative and outcome.returncode != 0):
            raise ValueError(f'{case} {key} fixture failed: {outcome.stdout[-700:]}')
        commands[key] = (command, outcome, log)
    pos, neg = commands['positive'], commands['negative']
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['held-out'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'command': '.venv-cpu/bin/python work/' + folder.name + '/acceptance_fixture.py --case ' + case,
        'test_exit_code': 0,
        'test_log': str(pos[2].relative_to(folder)), 'test_log_sha256': sha(pos[2]),
        'negative_command': '.venv-cpu/bin/python work/' + folder.name + '/acceptance_fixture.py --case ' + case + ' --negative',
        'negative_exit_code': neg[1].returncode, 'negative_expected_error': 'stale',
        'negative_log': str(neg[2].relative_to(folder)), 'negative_log_sha256': sha(neg[2]),
        'script': script.name, 'script_sha256': script_sha,
        'fixture_only': True,
    }
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
print('Bound source-decoding and stale-source fixture proofs for', len(manifest['cases']), 'exact cases')
