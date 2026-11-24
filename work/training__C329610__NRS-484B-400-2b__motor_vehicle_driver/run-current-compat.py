"""Run current public compatibility for six exact selected constructions."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-execution-manifest.json'
PUBLIC = HERE / 'current-public'
PUBLIC.mkdir(exist_ok=True)
DECODER = ROOT / '.runtime-work/c329610-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(item):
    suffix, candidate = item
    case = HERE.name + '__' + suffix
    name = suffix + '-' + candidate
    output = ROOT / '.runtime-work' / ('c329610-current-' + name + '-compat')
    if output.exists():
        shutil.rmtree(output)
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'compatibility', '--manifest', str(MANIFEST), '--case', case,
               '--candidate', candidate, '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)]
    env = dict(os.environ)
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    done = subprocess.run(command, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    log = PUBLIC / (name + '-command.log')
    log.write_text(done.stdout.rstrip() + '\n')
    if done.returncode:
        return {'case': suffix, 'candidate': candidate, 'exit_code': done.returncode,
                'log': log.relative_to(HERE).as_posix(), 'error': done.stdout[-1500:]}
    receipt = json.loads((output / 'compatibility.json').read_text())
    if not receipt.get('passed') or receipt['case_id'] != case or receipt['candidate_id'] != candidate:
        raise ValueError('Unexpected compatibility receipt for ' + name)
    files = {}
    for source, label in [('compatibility.json', 'compatibility.json'),
                          ('compatibility-analysis.log', 'analysis.log'),
                          ('negative-analysis.log', 'negative.log')]:
        target = PUBLIC / (name + '-' + label)
        shutil.copyfile(output / source, target)
        files[label] = {'path': target.relative_to(HERE).as_posix(), 'sha256': sha(target)}
    return {'case': suffix, 'candidate': candidate, 'exit_code': 0,
            'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
            'files': files, 'fixture_sha256': receipt['fixture_sha256'],
            'construction_sha256': receipt['construction_sha256']}


def main():
    items = [(suffix, candidate) for suffix in ('witness_1', 'witness_2')
             for candidate in ('primary', 'fallback1', 'fallback2')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, items))
    target = PUBLIC / 'candidate-compat-summary.json'
    target.write_text(json.dumps({'format': 'c329610-current-public-compatibility',
                                  'results': results}, indent=2) + '\n')
    for result in results:
        print(result['case'], result['candidate'], result['exit_code'], flush=True)
        if result['exit_code']:
            print(result['error'], file=sys.stderr)
    if any(result['exit_code'] for result in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
