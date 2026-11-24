"""Run and retain current public compatibility for both cases and risk variants."""
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
    name = suffix + '-' + candidate
    case_id = HERE.name + '__' + suffix
    output = ROOT / '.runtime-work/c405647-267-2f' / ('public-' + name)
    if output.exists():
        shutil.rmtree(output)
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'compatibility', '--manifest', str(MANIFEST), '--case', case_id,
               '--candidate', candidate, '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)]
    env = dict(os.environ)
    env['TMPDIR'] = str(ROOT / '.runtime-work/c405647-267-2f/tmp')
    env['MPLCONFIGDIR'] = str(ROOT / '.runtime-work/c405647-267-2f/mpl')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    done = subprocess.run(command, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1200)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    log = PUBLIC / (name + '-command.log')
    log.write_text(done.stdout.rstrip() + '\n')
    if done.returncode:
        return {'case': case_id, 'candidate': candidate,
                'exit_code': done.returncode, 'error': done.stdout[-1500:]}
    receipt = json.loads((output / 'compatibility.json').read_text())
    if not receipt.get('passed') or receipt['case_id'] != case_id or receipt['candidate_id'] != candidate:
        raise ValueError('Unexpected compatibility receipt for ' + name)
    files = {}
    for source, label in [('compatibility.json', 'compatibility.json'),
                          ('compatibility-analysis.log', 'analysis.log'),
                          ('negative-analysis.log', 'negative.log')]:
        target = PUBLIC / (name + '-' + label)
        shutil.copyfile(output / source, target)
        if source == 'compatibility.json' and sha(target) != sha(output / source):
            raise ValueError('Compatibility receipt changed on return')
        files[label] = {'path': target.relative_to(HERE).as_posix(),
                        'sha256': sha(target)}
    if files['analysis.log']['sha256'] != receipt['log_sha256'] or files['negative.log']['sha256'] != receipt['negative_log_sha256']:
        raise ValueError('Returned analysis log differs from source-bound receipt')
    return {'case': case_id, 'candidate': candidate, 'exit_code': 0,
            'files': files, 'construction_sha256': receipt['construction_sha256'],
            'fixture_sha256': receipt['fixture_sha256']}


def main():
    names = [(suffix, candidate)
             for suffix in ('controlled_1', 'controlled_2')
             for candidate in ('primary', 'fallback1', 'fallback2')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, names))
    report = {'format': 'c405647-2f-current-compatibility-matrix-v1',
              'results': results, 'all_passed': all(r['exit_code'] == 0 for r in results),
              'physical_acceptance': False}
    path = PUBLIC / 'public-matrix.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['all_passed'], 'results': len(results),
                      'sha256': sha(path)}))
    if not report['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
