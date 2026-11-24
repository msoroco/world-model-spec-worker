"""Run pinned offline construction checks on all current-runtime runner drafts."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'current-runtime-runner-draft-manifest.json'
SCRATCH = REPO / '.runtime-work/owner150142/current-runner-offline'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(case, candidate):
    short = case.removeprefix(ROOT.name + '__')
    target = SCRATCH / short / candidate
    target.mkdir(parents=True, exist_ok=True)
    output = target / 'bundle'
    log = target / 'offline.log'
    if output.exists():
        raise ValueError('Choose a fresh offline draft output: ' + str(output))
    command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
               '--manifest', str(MANIFEST), '--case', case,
               '--candidate', candidate, '--output', str(output)]
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(target / 'runtime-output')
    env['TMPDIR'] = str(target)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    with log.open('w') as stream:
        completed = subprocess.run(command, cwd=REPO, env=env,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=300)
    return {'case_id': case, 'candidate_id': candidate,
            'exit_code': completed.returncode,
            'log_sha256': sha(log),
            'log': str(log.relative_to(REPO))}


def run():
    if SCRATCH.exists():
        raise ValueError('Retain previous offline draft proof; choose fresh scratch')
    SCRATCH.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text())
    jobs = [(entry['case_id'], candidate)
            for entry in manifest['cases']
            for candidate in ['primary', *[item['id'] for item in entry['candidates']]]]
    if len(jobs) != 120:
        raise ValueError('Expected 120 exact draft candidates')
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(one, *job): job for job in jobs}
        rows = [future.result() for future in as_completed(futures)]
    rows.sort(key=lambda item: (item['case_id'], item['candidate_id']))
    if any(item['exit_code'] for item in rows):
        failures = [item for item in rows if item['exit_code']]
        raise ValueError('Current runner draft offline failed: ' + repr(failures))
    return {'format': 'c150142-current-runner-offline-index-v1',
            'passed': True, 'manifest_sha256': sha(MANIFEST),
            'candidates': len(rows), 'rows': rows,
            'scope': 'synthetic CPU offline checks; no CARLA or public compatibility',
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
