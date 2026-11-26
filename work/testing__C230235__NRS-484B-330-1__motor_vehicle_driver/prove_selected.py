"""Exercise exact primary and fallback bundles through pinned CPU runtime."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = ROOT / '.runtime-work' / 'c230235-owner-nov26b'
VALIDATOR = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_log(source, dest):
    lines = [line.rstrip() for line in Path(source).read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    Path(dest).write_text('\n'.join(lines) + '\n')
    return sha(dest)


def execute(command, env):
    result = subprocess.run(command, cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    if result.returncode:
        raise ValueError('CPU proof failed: ' + ' '.join(command) + '\n' + result.stdout[-3000:])
    return result


def prove():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, TMPDIR=str(SCRATCH / 'tmp'),
               MPLCONFIGDIR=str(SCRATCH / 'mpl'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    Path(env['MPLCONFIGDIR']).mkdir(parents=True, exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError('pinned Lean validator binary missing')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        short = case_id.removeprefix(HERE.name + '__')
        for candidate in ('primary', 'fallback1'):
            slot = entry if candidate == 'primary' else entry['candidates'][0]
            offline_dir = SCRATCH / ('offline-selected-' + short + '-' + candidate)
            if offline_dir.exists():
                shutil.rmtree(offline_dir)
            command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                       'offline', '--manifest', str(MANIFEST), '--case', case_id,
                       '--output', str(offline_dir), '--python', str(ROOT / '.venv-cpu/bin/python')]
            if candidate != 'primary':
                command += ['--candidate', candidate]
            execute(command, env)
            log = 'selected-offline-' + short + '-' + candidate + '.log'
            copy_log(offline_dir / 'offline.log', HERE / log)
            slot['offline'] = {'command': ' '.join(command), 'construction_sha256': slot['construction_sha256'],
                               'exit_code': 0, 'log': log, 'log_sha256': sha(HERE / log)}
            compatibility_dir = SCRATCH / ('compat-selected-' + short + '-' + candidate)
            if compatibility_dir.exists():
                shutil.rmtree(compatibility_dir)
            command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                       'compatibility', '--manifest', str(MANIFEST), '--case', case_id,
                       '--output', str(compatibility_dir), '--library', str(ROOT / 'runtime/library'),
                       '--validator', str(VALIDATOR)]
            if candidate != 'primary':
                command += ['--candidate', candidate]
            execute(command, env)
            prefix = 'selected-compat-' + short + '-' + candidate
            analysis_log, negative_log, receipt_file = (prefix + suffix for suffix in
                                                         ('-analysis.log', '-negative.log', '-receipt.json'))
            copy_log(compatibility_dir / 'compatibility-analysis.log', HERE / analysis_log)
            copy_log(compatibility_dir / 'negative-analysis.log', HERE / negative_log)
            receipt = json.loads((compatibility_dir / 'compatibility.json').read_text())
            receipt['log_sha256'] = sha(HERE / analysis_log)
            receipt['negative_log_sha256'] = sha(HERE / negative_log)
            (HERE / receipt_file).write_text(json.dumps(receipt, sort_keys=True,
                                                         separators=(',', ':')) + '\n')
            slot['compatibility'] = {'command': ' '.join(command),
                                     'receipt': receipt_file, 'sha256': sha(HERE / receipt_file),
                                     'log': analysis_log, 'negative_log': negative_log,
                                     'negative_log_sha256': sha(HERE / negative_log)}
            if candidate == 'primary':
                entry['negative'] = {'log': negative_log}
            print(short, candidate, 'offline and compatibility passed', flush=True)
        MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print('proved', prove())
