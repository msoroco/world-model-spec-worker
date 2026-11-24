"""Refresh selected reference/contrast CPU receipts for the pinned runtime revision."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c229597-library-current/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_id, candidate_id):
    suffix = case_id.rsplit('__', 1)[-1]
    output = ROOT / '.runtime-work' / ('c229597-selected-' + suffix + '-' + candidate_id + '-current-v2')
    command_log = ROOT / '.runtime-work' / ('c229597-selected-' + suffix + '-' + candidate_id + '-current-v2.log')
    command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
               '--manifest', str(MANIFEST), '--case', case_id, '--candidate', candidate_id,
               '--output', str(output), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    env = dict(os.environ, TMPDIR=str(ROOT / '.runtime-work'), PYTHONDONTWRITEBYTECODE='1')
    with command_log.open('w') as stream:
        process = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if process.returncode:
        raise RuntimeError(f'{case_id}/{candidate_id}: exit {process.returncode}; {command_log}')
    proof = json.loads((output / 'compatibility.json').read_text())
    if (proof.get('passed') is not True or proof.get('case_id') != case_id
            or proof.get('candidate_id') != candidate_id):
        raise ValueError(f'Compatibility receipt differs: {case_id}/{candidate_id}')
    dest = PACKAGE / 'selected-proofs' / suffix / candidate_id
    dest.mkdir(parents=True, exist_ok=True)
    for source, target in [('compatibility.json', 'compatibility.json'),
                           ('compatibility-analysis.log', 'analysis.log'),
                           ('negative-analysis.log', 'negative.log')]:
        shutil.copyfile(output / source, dest / target)
    spec = {'receipt': 'selected-proofs/' + suffix + '/' + candidate_id + '/compatibility.json',
            'sha256': sha(dest / 'compatibility.json'),
            'log': 'selected-proofs/' + suffix + '/' + candidate_id + '/analysis.log',
            'negative_log': 'selected-proofs/' + suffix + '/' + candidate_id + '/negative.log'}
    return case_id, candidate_id, spec, proof


def main():
    manifest = json.loads(MANIFEST.read_text())
    jobs = [(entry['case_id'], candidate)
            for entry in manifest['cases'] if entry['case_id'].endswith(('__reference', '__contrast'))
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')]
    if len(jobs) != 8:
        raise ValueError('Expected eight selected compatibility jobs')
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(run, case_id, candidate): (case_id, candidate)
                   for case_id, candidate in jobs}
        for future in concurrent.futures.as_completed(futures):
            case_id, candidate_id, spec, proof = future.result()
            entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
            target = entry if candidate_id == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate_id)
            if proof['construction_sha256'] != target['construction_sha256']:
                raise ValueError(f'Construction hash differs: {case_id}/{candidate_id}')
            target['compatibility'] = spec
            if candidate_id == 'primary':
                entry['negative'] = {'log': spec['negative_log']}
            records.append({'case_id': case_id, 'candidate_id': candidate_id,
                            'receipt_sha256': spec['sha256'], 'passed': True})
            print(case_id, candidate_id, 'passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    (PACKAGE / 'selected-current-cpu-index.json').write_text(json.dumps({
        'format': 'c229597-selected-current-compatibility-v1',
        'manifest_sha256': sha(MANIFEST), 'records': sorted(records, key=lambda x: (x['case_id'], x['candidate_id'])),
        'software_compatibility_passed': True, 'native_executed': False,
        'delivery_ready': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()
