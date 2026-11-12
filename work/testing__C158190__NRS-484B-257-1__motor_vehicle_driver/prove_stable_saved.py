"""Replay compatibility and recorded-only processing against one unchanged manifest."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def run_one(entry, ident, manifest_sha):
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    stem = f'c158190-{suffix}-{ident}-stable-v1'
    attempt = REPO / '.runtime-work' / (stem + '-compat')
    output = REPO / '.runtime-work' / (stem + '-saved')
    folder = (ROOT / (entry['construction'] if ident == 'primary' else
                      next(c['construction'] for c in entry['candidates'] if c['id'] == ident))).parent
    prefix = 'primary' if ident == 'primary' else ident
    common = ['--manifest', str(MANIFEST), '--case', entry['case_id']]
    command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
               'compatibility', *common]
    if ident != 'primary':
        command += ['--candidate', ident]
    command += ['--output', str(attempt), '--library', str(REPO / 'runtime/library'),
                '--validator', str(VALIDATOR)]
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c158190-output-root-20261111')
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    (folder / f'{prefix}-stable-compatibility.log').write_text(result.stdout[-30000:] + result.stderr[-30000:])
    if result.returncode:
        raise ValueError(f'{suffix} {ident}: stable compatibility exited {result.returncode}')
    receipt = json.loads((attempt / 'compatibility.json').read_text())
    if not receipt.get('passed') or receipt.get('candidate_id') != ident:
        raise ValueError(f'{suffix} {ident}: stable compatibility receipt failed')
    saved_command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                     'process-saved', *common, '--attempt', str(attempt),
                     '--output', str(output), '--library', str(REPO / 'runtime/library'),
                     '--validator', str(VALIDATOR)]
    saved_result = subprocess.run(saved_command, cwd=REPO, env=env, capture_output=True, text=True)
    (folder / f'{prefix}-stable-saved.log').write_text(saved_result.stdout[-30000:] + saved_result.stderr[-30000:])
    if saved_result.returncode:
        raise ValueError(f'{suffix} {ident}: stable process-saved exited {saved_result.returncode}')
    versions = sorted(output.glob('v*/processing.json'))
    if len(versions) != 1:
        raise ValueError(f'{suffix} {ident}: unexpected saved processing versions')
    saved = json.loads(versions[0].read_text())
    if saved.get('recorded_only') is not True or saved.get('physical_acceptance_claimed'):
        raise ValueError(f'{suffix} {ident}: saved processing claims physical acceptance')
    if hashlib.sha256(MANIFEST.read_bytes()).hexdigest() != manifest_sha:
        raise ValueError('Manifest changed during stable proof run')
    return {'case': suffix, 'candidate': ident, 'compatibility': True,
            'recorded_only': True, 'physical_acceptance_claimed': False,
            'manifest_sha256': manifest_sha}


def main():
    manifest_sha = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    manifest = json.loads(MANIFEST.read_text())
    tasks = [(entry, ident) for entry in manifest['cases']
             for ident in ('primary', *(candidate['id'] for candidate in entry['candidates']))]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_one, entry, ident, manifest_sha) for entry, ident in tasks]
        errors = []
        for future in as_completed(futures):
            try:
                print(json.dumps(future.result()), flush=True)
            except Exception as error:
                errors.append(str(error))
                print(json.dumps({'error': str(error)}), flush=True)
    if errors:
        raise ValueError('; '.join(errors))


if __name__ == '__main__':
    main()
