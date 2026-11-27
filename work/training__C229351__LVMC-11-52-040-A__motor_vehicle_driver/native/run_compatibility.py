"""Run and retain the exact selected diagnostic compatibility receipts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'
DECODER = ROOT / '.runtime-work/c229351-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(entry, candidate, output):
    directory = FOLDER / 'compatibility'
    directory.mkdir(exist_ok=True)
    label = entry['case_id'].rsplit('__', 1)[-1] + '-' + candidate
    files = {'receipt': 'compatibility.json', 'log': 'compatibility-analysis.log',
             'negative_log': 'negative-analysis.log'}
    spec = {}
    for key, name in files.items():
        destination = directory / (label + '-' + name)
        shutil.copy2(output / name, destination)
        spec[key] = str(destination.relative_to(FOLDER))
    spec['sha256'] = sha(FOLDER / spec['receipt'])
    if candidate == 'primary':
        entry['compatibility'] = spec
        entry['negative'] = {'log': spec['negative_log']}
    else:
        entry['candidates'][0]['compatibility'] = spec


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work'))
    for index, entry in enumerate(manifest['cases']):
        for candidate in ('primary', 'fallback1'):
            output = ROOT / f'.runtime-work/c229351-compat-v2-{index}-{candidate}'
            if index == 0 and candidate == 'primary':
                if not (output / 'compatibility.json').is_file():
                    raise ValueError('First compatibility receipt missing')
            else:
                command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                           'compatibility', '--manifest', str(MANIFEST),
                           '--case', entry['case_id'], '--candidate', candidate,
                           '--output', str(output), '--library', str(ROOT / 'runtime/library'),
                           '--validator', str(DECODER)]
                log = ROOT / f'.runtime-work/c229351-compat-v2-{index}-{candidate}.log'
                with log.open('w') as stream:
                    result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                            stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(f'{index} {candidate} failed; see {log}')
            bind(entry, candidate, output)
            MANIFEST.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
            print(f'{index} {candidate} passed and bound', flush=True)


if __name__ == '__main__':
    main()
