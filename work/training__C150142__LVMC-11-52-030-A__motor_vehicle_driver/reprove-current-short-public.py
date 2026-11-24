"""Run selected short-case public compatibility with a pinned scratch decoder."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
SCRATCH = ROOT / '.runtime-work' / 'owner150142'
MANIFEST = WORK / 'execution-manifest.json'
VALIDATOR = SCRATCH / 'current-decoder/.lake/build/bin/adapterCheck'
VARS = ('primary', 'fallback1', 'fallback2', 'fallback3')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(item):
    short, candidate = item
    case = WORK.name + '__' + short
    output = SCRATCH / f'{short}-{candidate}-current-public'
    log = SCRATCH / f'{short}-{candidate}-current-public.log'
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'compatibility', '--manifest', str(MANIFEST), '--case', case,
               '--candidate', candidate, '--output', str(output),
               '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / f'env-{short}-{candidate}'),
               MPLCONFIGDIR=str(SCRATCH / 'mpl'))
    with log.open('w') as stream:
        proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                              stderr=subprocess.STDOUT)
    if proc.returncode:
        shutil.copyfile(log, WORK / f'current-{short}-{candidate}-public-error.log')
        return {'case': short, 'candidate': candidate, 'exit_code': proc.returncode,
                'error_log': f'current-{short}-{candidate}-public-error.log'}
    saved = {}
    for source, suffix in (('compatibility.json', 'compatibility.json'),
                           ('compatibility-analysis.log', 'analysis.log'),
                           ('negative-analysis.log', 'negative.log')):
        target = WORK / f'current-{short}-{candidate}-{suffix}'
        shutil.copyfile(output / source, target)
        saved[source] = {'file': target.name, 'sha256': digest(target)}
    retained_log = WORK / f'current-{short}-{candidate}-public.log'
    shutil.copyfile(log, retained_log)
    receipt = json.loads((output / 'compatibility.json').read_text())
    assert receipt['passed'] and receipt['candidate_id'] == candidate
    return {'case': short, 'candidate': candidate, 'exit_code': 0,
            'construction_sha256': receipt['construction_sha256'],
            'public_log': retained_log.name, 'public_log_sha256': digest(retained_log),
            'saved': saved}


def main():
    if not VALIDATOR.is_file():
        raise ValueError('Build current pinned decoder first')
    manifest = json.loads(MANIFEST.read_text())
    selected = []
    for entry in manifest['cases']:
        short = entry['case_id'].split('__')[-1]
        if short in ('reference', 'contrast') or short.startswith(('tour_bus_',
                   'shuttle_bus_', 'rtc_bus_', 'limo_')):
            continue
        selected.extend((short, candidate) for candidate in VARS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, selected))
    output = {'format': 'c150142-current-short-public-reproof-v1',
              'scope': 'synthetic source-bound CPU compatibility',
              'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
              'selected_manifest_sha256': digest(MANIFEST),
              'results': results, 'passed': all(x['exit_code'] == 0 for x in results)}
    target = WORK / 'current-short-public-reproof-index.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': output['passed'], 'count': len(results),
                      'failures': [x for x in results if x['exit_code']],
                      'index_sha256': digest(target)}))
    if not output['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
