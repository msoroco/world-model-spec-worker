"""Execute recorded-only processing for every current selected construction."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

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
    attempt = ROOT / '.runtime-work/c405647-267-2f' / ('public-' + name)
    output = ROOT / '.runtime-work/c405647-267-2f' / ('saved-' + name)
    if output.exists():
        shutil.rmtree(output)
    source_receipt = json.loads((attempt / 'compatibility.json').read_text())
    if not source_receipt.get('passed') or source_receipt['case_id'] != case_id:
        raise ValueError('Current compatibility proof missing: ' + name)
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'process-saved', '--manifest', str(MANIFEST), '--case', case_id,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)]
    env = dict(os.environ)
    env['TMPDIR'] = str(ROOT / '.runtime-work/c405647-267-2f/tmp')
    env['MPLCONFIGDIR'] = str(ROOT / '.runtime-work/c405647-267-2f/mpl')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    done = subprocess.run(command, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1200)
    log = PUBLIC / (name + '-saved.log')
    log.write_text(done.stdout.rstrip() + '\n')
    result = {'case_id': case_id, 'candidate_id': candidate,
              'command': ' '.join(command), 'exit_code': done.returncode,
              'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log)}
    if done.returncode:
        result['error'] = done.stdout[-1500:]
        return result
    receipt_path = output / 'v0001/processing.json'
    receipt = json.loads(receipt_path.read_text())
    if not (receipt['passed'] and receipt['recorded_only'] and
            receipt['originals_preserved'] and not receipt['missing_evidence'] and
            receipt['analysis_revision']['construction_sha256'] == source_receipt['construction_sha256']):
        raise ValueError('Saved processor did not preserve source-bound analysis: ' + name)
    target = PUBLIC / (name + '-processing.json')
    shutil.copyfile(receipt_path, target)
    result['receipt'] = target.relative_to(HERE).as_posix()
    result['receipt_sha256'] = sha(target)
    return result


def main():
    names = [(suffix, candidate)
             for suffix in ('controlled_1', 'controlled_2')
             for candidate in ('primary', 'fallback1', 'fallback2')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, names))
    path = PUBLIC / 'saved-matrix.json'
    path.write_text(json.dumps({'format': 'c405647-2f-current-saved-matrix-v1',
                                'results': results,
                                'all_passed': all(r['exit_code'] == 0 for r in results),
                                'diagnostic_only': True}, indent=2) + '\n')
    print(json.dumps({'saved_cases': len(results),
                      'all_passed': all(r['exit_code'] == 0 for r in results),
                      'sha256': sha(path)}))
    if any(r['exit_code'] != 0 for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
