"""Run all 16 long cases and 64 candidates against the selected current runtime."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
OUTPUT = REPO / '.runtime-work/owner150142/current-selected-long-offline-v1'
LOGS = HERE / 'current-selected-long-offline'
INDEX = HERE / 'current-selected-long-offline-index.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task(job):
    case, candidate, construction_hash = job
    suffix = case.removeprefix(HERE.name + '__')
    output = OUTPUT / suffix / candidate
    log = LOGS / suffix / (candidate + '.log')
    command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
               '--manifest', str(MANIFEST), '--case', case,
               '--candidate', candidate, '--output', str(output),
               '--python', sys.executable]
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(OUTPUT / 'scenario-output')
    env['TMPDIR'] = str(OUTPUT / 'tmp')
    (OUTPUT / 'tmp').mkdir(parents=True, exist_ok=True)
    run = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                         env=env, timeout=300)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text((run.stdout + run.stderr).rstrip() + '\n')
    if run.returncode:
        raise ValueError('Current long offline failed: ' + suffix + '/' + candidate)
    proof = json.loads(run.stdout)
    if (proof.get('offline_passed') is not True or
            proof.get('simulation_started') is not False or
            proof.get('case_id') != case or proof.get('candidate_id') != candidate):
        raise ValueError('Current long offline identity differs: ' + suffix + '/' + candidate)
    return {'case_id': case, 'candidate_id': candidate,
            'construction_sha256': construction_hash,
            'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    runtime = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    if (manifest['runtime_manifest_sha256'] != runtime or
            manifest['delivery_ready'] is not False):
        raise ValueError('Selected manifest does not bind current partial runtime')
    jobs = []
    for entry in manifest['cases']:
        if entry.get('fixture_recipe'):
            continue
        fields = [('primary', entry)] + [(row['id'], row) for row in entry['candidates']]
        if len(fields) != 4:
            raise ValueError('Long candidate count differs')
        jobs.extend((entry['case_id'], candidate, field['construction_sha256'])
                    for candidate, field in fields)
    if len(jobs) != 64:
        raise ValueError('Expected 64 long current selected candidates')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(task, jobs))
    INDEX.write_text(json.dumps({
        'format': 'c150142-current-selected-long-offline-v1',
        'runtime_manifest_sha256': runtime,
        'selected_manifest_sha256': sha(MANIFEST),
        'rows': rows, 'original_native_observed': False,
    }, indent=2) + '\n')
    print(json.dumps({'candidates': len(rows), 'index_sha256': sha(INDEX),
                      'runtime_manifest_sha256': runtime}, sort_keys=True))


if __name__ == '__main__':
    main()
