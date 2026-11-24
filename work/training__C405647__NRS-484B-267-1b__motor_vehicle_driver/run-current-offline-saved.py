"""Refresh active-runtime offline and recorded-only proofs for selected candidates."""
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
DECODER = ROOT / '.runtime-work/c329610-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(item):
    suffix, candidate = item
    case = HERE.name + '__' + suffix
    name = suffix + '-' + candidate
    offline = ROOT / '.runtime-work' / ('c405647-current-' + name + '-offline')
    saved = ROOT / '.runtime-work' / ('c405647-current-' + name + '-saved')
    attempt = ROOT / '.runtime-work' / ('c405647-current-' + name + '-compat')
    for destination in (offline, saved):
        if destination.exists():
            shutil.rmtree(destination)
    env = dict(os.environ)
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    base = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py')]
    commands = {
        'offline': base + ['offline', '--manifest', str(MANIFEST), '--case', case,
                           '--candidate', candidate, '--output', str(offline),
                           '--python', str(ROOT / '.venv-cpu/bin/python')],
        'saved': base + ['process-saved', '--manifest', str(MANIFEST), '--case', case,
                         '--attempt', str(attempt), '--output', str(saved),
                         '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)]}
    result = {'case': suffix, 'candidate': candidate}
    for stage, command in commands.items():
        done = subprocess.run(command, cwd=ROOT, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
        log = PUBLIC / (name + '-' + stage + '.log')
        log.write_text(done.stdout.rstrip() + '\n')
        result[stage] = {'exit_code': done.returncode,
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log)}
        if done.returncode:
            result[stage]['error'] = done.stdout[-1500:]
            break
        if stage == 'saved':
            processing = saved / 'v0001/processing.json'
            target = PUBLIC / (name + '-processing.json')
            shutil.copyfile(processing, target)
            result[stage]['receipt'] = target.relative_to(HERE).as_posix()
            result[stage]['receipt_sha256'] = sha(target)
    return result


def main():
    items = [(suffix, candidate) for suffix in ('reference', 'contrast')
             for candidate in ('primary', 'fallback1', 'fallback2')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, items))
    target = PUBLIC / 'candidate-saved-summary.json'
    target.write_text(json.dumps({'format': 'c405647-current-offline-saved',
                                  'results': results}, indent=2) + '\n')
    for result in results:
        print(result['case'], result['candidate'],
              result.get('offline', {}).get('exit_code'),
              result.get('saved', {}).get('exit_code'), flush=True)
        for stage in ('offline', 'saved'):
            if result.get(stage, {}).get('exit_code'):
                print(result[stage]['error'], file=sys.stderr)
    if any(result.get(stage, {}).get('exit_code') != 0
           for result in results for stage in ('offline', 'saved')):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
