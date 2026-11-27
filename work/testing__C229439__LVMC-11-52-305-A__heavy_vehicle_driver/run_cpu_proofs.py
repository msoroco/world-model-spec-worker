"""Retain exact offline and positive/negative compatibility receipts per candidate."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/lvmc305-proofs-v1'
PYTHON = REPO / '.venv-cpu/bin/python'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'mpl').mkdir(exist_ok=True)
    (SCRATCH / 'pipeline-output').mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'pipeline-output'),
               MPLCONFIGDIR=str(SCRATCH / 'mpl'))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            output = SCRATCH / (suffix + '-' + candidate)
            output.mkdir(exist_ok=True)
            offline = [str(PYTHON), str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(output / 'offline'),
                       '--python', str(PYTHON)]
            process = subprocess.run(offline, cwd=REPO, env=env, capture_output=True, text=True)
            log = ROOT / ('cpu-offline-' + suffix + '-' + candidate + '.log')
            log.write_text((process.stdout + process.stderr).rstrip() + '\n')
            if process.returncode:
                raise RuntimeError('offline ' + suffix + ' ' + candidate + ': ' + log.read_text()[-1500:])
            selected['offline'] = {'command': ' '.join(offline), 'exit_code': 0,
                                   'log': log.name, 'log_sha256': sha(log),
                                   'construction_sha256': selected['construction_sha256']}
            command = [str(PYTHON), str(REPO / 'runtime.py'), 'compatibility',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate, '--output', str(output / 'compat'),
                       '--library', str(REPO / 'runtime/library'),
                       '--validator', str(VALIDATOR)]
            process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            if process.returncode:
                failure = ROOT / ('cpu-compatibility-' + suffix + '-' + candidate + '-failure.log')
                failure.write_text((process.stdout + process.stderr).rstrip() + '\n')
                raise RuntimeError('compatibility ' + suffix + ' ' + candidate + ': ' + failure.read_text()[-1500:])
            receipt = ROOT / ('cpu-compatibility-' + suffix + '-' + candidate + '.json')
            shutil.copyfile(output / 'compat/compatibility.json', receipt)
            analysis = ROOT / ('cpu-compatibility-analysis-' + suffix + '-' + candidate + '.log')
            negative = ROOT / ('cpu-compatibility-negative-' + suffix + '-' + candidate + '.log')
            shutil.copyfile(output / 'compat/compatibility-analysis.log', analysis)
            shutil.copyfile(output / 'compat/negative-analysis.log', negative)
            proof = json.loads(receipt.read_text())
            if proof['log_sha256'] != sha(analysis) or proof['negative_log_sha256'] != sha(negative):
                raise RuntimeError('retained compatibility logs differ')
            selected['compatibility'] = {'command': ' '.join(command),
                                          'receipt': receipt.name,
                                          'sha256': sha(receipt),
                                          'log': analysis.name,
                                          'negative_log': negative.name}
            selected['negative'] = {'log': negative.name}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            print(suffix, candidate, 'passed', flush=True)


if __name__ == '__main__':
    run()
