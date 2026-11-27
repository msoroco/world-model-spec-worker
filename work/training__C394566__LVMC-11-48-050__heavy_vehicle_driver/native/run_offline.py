"""Run every exact selected candidate's CPU offline check and bind its log."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
MANIFEST = FOLDER / 'execution-probe-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(item):
    case, candidate, construction_sha = item
    suffix = case.removeprefix(FOLDER.name + '__')
    scratch = ROOT / '.runtime-work' / ('c394566-offline-v17-' + suffix + '-' + candidate)
    if scratch.exists():
        raise ValueError('Fresh offline scratch required: ' + str(scratch))
    command = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(ROOT / 'runtime.py'), 'offline',
               '--manifest', str(MANIFEST), '--case', case, '--candidate', candidate,
               '--output', str(scratch), '--python', str(ROOT / '.venv-cpu/bin/python')]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch))
    completed = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=300)
    if completed.returncode:
        raise ValueError('Offline failed for ' + suffix + '/' + candidate + ': ' + completed.stdout[-1200:])
    target = FOLDER / 'offline/selected' / (suffix + '-' + candidate + '.log')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(scratch / 'offline.log', target)
    proof = {'command': ' '.join(command), 'exit_code': 0, 'construction_sha256': construction_sha,
             'log': str(target.relative_to(FOLDER)), 'log_sha256': sha(target)}
    return case, candidate, proof


def main():
    manifest = json.loads(MANIFEST.read_text())
    items = []
    for entry in manifest['cases']:
        items.append((entry['case_id'], 'primary', entry['construction_sha256']))
        items.extend((entry['case_id'], c['id'], c['construction_sha256']) for c in entry['candidates'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        proofs = list(pool.map(check, items))
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    for case, candidate, proof in proofs:
        entry = by_case[case]
        if candidate == 'primary':
            entry['offline'] = proof
        else:
            next(c for c in entry['candidates'] if c['id'] == candidate)['offline'] = proof
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'candidate_offline_checks': len(proofs)}))


if __name__ == '__main__':
    main()
