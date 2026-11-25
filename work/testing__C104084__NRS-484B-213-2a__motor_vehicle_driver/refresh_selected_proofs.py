"""Refresh source-bound CPU proofs after authored implementation changes."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PYTHON = REPO / '.venv-cpu/bin/python'
VERSION = 'v6'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, env):
    result = subprocess.run([str(item) for item in command], cwd=REPO, env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, command)) + '\n' + result.stdout[-1500:])
    return result.stdout


def copy_log(source, target):
    content = source.read_text().rstrip('\n')
    target.write_text(content + ('\n' if content else ''))
    return sha(target)


def main():
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work/c104084-tmp'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c104084-output'),
               PYTHONPATH=str(REPO / 'runtime/scenario_pipeline') + ':' +
                          str(REPO / 'runtime/python'))
    run((PYTHON, HERE / 'build_constructions.py'), env)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        entry['construction_sha256'] = sha(HERE / entry['construction'])
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    run((PYTHON, HERE / 'build_fallbacks.py'), env)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            prefix = 'primary' if candidate == 'primary' else 'fallback'
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            output = REPO / f'.runtime-work/c104084-{prefix}-offline-{suffix}-{VERSION}'
            command = (PYTHON, REPO / 'runtime.py', 'offline', '--manifest', MANIFEST,
                       '--case', entry['case_id'], '--candidate', candidate,
                       '--output', output, '--python', PYTHON)
            run(command, env)
            log = HERE / f'proof-{prefix}-offline-{suffix}.log'
            selected['offline'] = {'exit_code': 0,
                'construction_sha256': selected['construction_sha256'],
                'command': ' '.join(map(str, command)), 'log': log.name,
                'log_sha256': copy_log(output / 'offline.log', log)}
        output = REPO / f'.runtime-work/c104084-physical-{suffix}-{VERSION}'
        command = (PYTHON, HERE / 'physical_probe.py', '--case', entry['case_id'],
                   '--output', output)
        stdout = run(command, env)
        log = HERE / f'physical-{suffix}.log'
        log.write_text(stdout.rstrip('\n') + '\n')
        proof = {'construction_sha256': entry['construction_sha256'],
                 'fixtures': [], 'lifecycle': {'events': ['capture_finished',
                    'encoders_closed', 'restoration_verified', 'native_exit',
                    'owner_released', 'saved_processing_started'], 'exit_code': 0,
                    'log': log.name, 'log_sha256': sha(log)},
                 'scope': 'Synthetic CPU motion and lifecycle protocol only; physical crest not claimed'}
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = HERE / f'physical-{suffix}-{kind}.json'
            proof['fixtures'].append({'kind': kind, 'command': ' '.join(map(str, command)),
                'exit_code': 0, 'log': log.name, 'log_sha256': sha(log),
                'result': result.name, 'result_sha256': sha(result)})
        receipt = HERE / f'physical-{suffix}-proof.json'
        receipt.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
        entry['physical_preparation'] = {'receipt': receipt.name, 'sha256': sha(receipt)}
        print(suffix, 'offline+physical passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            prefix = 'primary' if candidate == 'primary' else 'fallback'
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            output = REPO / f'.runtime-work/c104084-{prefix}-compat-{suffix}-{VERSION}'
            command = (PYTHON, REPO / 'runtime.py', 'compatibility', '--manifest',
                       MANIFEST, '--case', entry['case_id'], '--candidate', candidate,
                       '--output', output, '--library', REPO / 'runtime/library',
                       '--validator', REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck')
            run(command, env)
            receipt = json.loads((output / 'compatibility.json').read_text())
            log = HERE / f'proof-{prefix}-compat-{suffix}.log'
            negative = HERE / f'proof-{prefix}-negative-{suffix}.log'
            receipt['log_sha256'] = copy_log(output / 'compatibility-analysis.log', log)
            receipt['negative_log_sha256'] = copy_log(output / 'negative-analysis.log', negative)
            proof = HERE / f'proof-{prefix}-compat-{suffix}.json'
            proof.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
            selected['compatibility'] = {'receipt': proof.name, 'sha256': sha(proof),
                                         'log': log.name}
            if candidate == 'fallback1':
                selected['compatibility']['negative_log'] = negative.name
            else:
                entry['negative'] = {'log': negative.name}
            print(suffix, candidate, 'compatibility passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
