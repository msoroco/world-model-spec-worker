"""Run source-bound CPU motion fixtures for every selected fire-lane case."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'))
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        fixtures = []
        for kind in KINDS:
            source = REPO / '.runtime-work' / ('c150099-physical-' + suffix + '-' + kind + '-v3')
            result = ROOT / ('cpu-physical-' + suffix + '-' + kind + '.json')
            log = ROOT / ('cpu-physical-' + suffix + '-' + kind + '.log')
            command = [str(REPO / '.venv-cpu/bin/python'), str(ROOT / 'physical_probe.py'),
                       '--case', case, '--kind', kind, '--source', str(source),
                       '--result', str(result)]
            run = subprocess.run(command, cwd=REPO, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(run.stdout.rstrip() + '\n')
            if run.returncode:
                raise ValueError('physical fixture failed: ' + suffix + ' ' + kind +
                                 '\n' + run.stdout[-1200:])
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.name, 'log_sha256': sha(log),
                             'result': result.name, 'result_sha256': sha(result)})
        entry['physical_preparation'] = {
            'receipt': 'cpu-physical-' + suffix + '-receipt.json'}
        life_log = ROOT / ('cpu-lifecycle-' + suffix + '.log')
        life_command = [str(REPO / '.venv-cpu/bin/python'), str(ROOT / 'prove_lifecycle.py'),
                        '--case', case, '--construction',
                        str(ROOT / 'cases' / suffix / 'construction.json'), '--scratch',
                        str(REPO / '.runtime-work' / ('c150099-lifecycle-' + suffix + '-v2'))]
        life_env = dict(env, PYTHONPATH=str(REPO / 'runtime'),
                        SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work' /
                                                          ('c150099-lifecycle-output-' + suffix)))
        life_run = subprocess.run(life_command, cwd=REPO, env=life_env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        life_log.write_text(life_run.stdout.rstrip() + '\n')
        if life_run.returncode:
            raise ValueError('lifecycle fixture failed: ' + suffix + '\n' + life_run.stdout[-1200:])
        life_result = json.loads(life_run.stdout)
        expected_events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                           'native_exit', 'owner_released', 'saved_processing_started']
        if life_result['events'] != expected_events or not all(
                life_result[k] for k in ('saved_only_rejected_before_owner_release',
                                          'native_exit_rejected_before_encoder_closure',
                                          'owner_release_rejected_before_native_exit',
                                          'pinned_closure_accepted_after_release')):
            raise ValueError('lifecycle fixture evidence incomplete: ' + suffix)
        receipt = {'format': 'worker-fire-lane-physical-diagnostic-proof',
                   'case_id': case, 'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures, 'diagnostic_fixture': True,
                   'physical_acceptance_claimed': False,
                   'lifecycle': {'events': expected_events, 'exit_code': 0,
                                 'command': ' '.join(life_command),
                                 'log': life_log.name, 'log_sha256': sha(life_log),
                                 'diagnostic_fixture': True,
                                 'original_owner_release_claimed': False}}
        path = ROOT / entry['physical_preparation']['receipt']
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        entry['physical_preparation']['sha256'] = sha(path)
        print('physical fixture states passed:', suffix, flush=True)
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
