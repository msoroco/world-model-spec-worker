"""Bind three diagnostic physical states and the pinned Native closure gate."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c158208-nov25/physical'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def run(command, log, env):
    process = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(process.stdout.rstrip() + '\n')
    if process.returncode:
        raise ValueError('physical diagnostic failed: ' + process.stdout[-1400:])


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(REPO / 'runtime') + ':' + str(REPO / 'runtime/scenario_pipeline'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c158208-nov25/output'),
               TMPDIR=str(REPO / '.runtime-work/c158208-nov25/tmp'))
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            location = SCRATCH / (suffix + '-' + kind + '-v1.json')
            history = None if kind == 'missing_evidence' else [
                {'frame': 0, 'ego_leading_station_m': -3, 'ego_full_body_clear': False},
                {'frame': 1, 'ego_leading_station_m': 1, 'ego_full_body_clear': False},
                {'frame': 2, 'ego_leading_station_m': 6 if kind == 'complete_motion' else 1,
                 'ego_full_body_clear': kind == 'complete_motion'}]
            write(location, {'case_id': case, 'diagnostic_fixture': True,
                             'entry_station_m': 0, 'body_history': history})
            result = ROOT / f'cpu-physical-{suffix}-{kind}.json'
            log = ROOT / f'cpu-physical-{suffix}-{kind}.log'
            command = [sys.executable, str(ROOT / 'physical_probe.py'), '--case', case,
                       '--fixture', str(location), '--result', str(result)]
            run(command, log, env)
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.name, 'log_sha256': sha(log),
                             'result': result.name, 'result_sha256': sha(result)})
        lifecycle_log = ROOT / f'cpu-lifecycle-{suffix}.log'
        lifecycle_command = [sys.executable, str(ROOT / 'prove_lifecycle.py'),
                             '--case', case, '--construction',
                             str(ROOT / entry['construction']), '--scratch',
                             str(SCRATCH / (suffix + '-lifecycle-v9'))]
        run(lifecycle_command, lifecycle_log, env)
        events = json.loads(lifecycle_log.read_text())['events']
        receipt = {'format': 'worker-yield-physical-diagnostic-proof',
                   'case_id': case, 'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                   'fixtures': fixtures,
                   'lifecycle': {'command': ' '.join(lifecycle_command), 'exit_code': 0,
                                 'events': events, 'log': lifecycle_log.name,
                                 'log_sha256': sha(lifecycle_log),
                                 'original_owner_release_claimed': False}}
        receipt_path = ROOT / f'cpu-physical-{suffix}-receipt.json'
        write(receipt_path, receipt)
        entry['physical_preparation'] = {'receipt': receipt_path.name,
                                         'sha256': sha(receipt_path)}
        print('physical diagnostic passed:', suffix, flush=True)
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
