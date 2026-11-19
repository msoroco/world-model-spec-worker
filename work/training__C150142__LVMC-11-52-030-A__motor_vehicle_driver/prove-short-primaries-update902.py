"""Run pinned current-runtime CPU chains for short selected primaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
OUT = ROOT / '.runtime-work/c150142-update902'
RUNTIME = ROOT / 'runtime.py'
PY = ROOT / '.venv-cpu/bin/python'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, phase, args):
    log = HERE / f'update902-{case}-{phase}.log'
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(OUT / 'runtime')
    with log.open('w') as stream:
        result = subprocess.run([str(PY), str(RUNTIME), phase, *map(str, args)],
                                cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{case} {phase} failed: {result.returncode}; {log}')
    return {'phase': phase, 'log': str(log.relative_to(ROOT)), 'sha256': sha(log)}


def main():
    cases = json.loads(MANIFEST.read_text())['cases']
    proof = []
    for entry in cases:
        if not entry.get('fixture_recipe'):
            continue
        case_id = entry['case_id']
        case = case_id.removeprefix(HERE.name + '__')
        if case == 'reference':
            continue  # Update 900/901 already proved this primary.
        base = OUT / case / 'primary'
        offline = run(case, 'offline', ['--manifest', MANIFEST, '--case', case_id,
                                       '--candidate', 'primary', '--output', base / 'offline'])
        compat = run(case, 'compatibility', ['--manifest', MANIFEST, '--case', case_id,
                                            '--candidate', 'primary', '--library', LIBRARY,
                                            '--validator', VALIDATOR, '--output', base / 'compatibility'])
        saved = run(case, 'process-saved', ['--manifest', MANIFEST, '--case', case_id,
                                           '--attempt', base / 'compatibility', '--library', LIBRARY,
                                           '--validator', VALIDATOR, '--output', base / 'saved'])
        saved_receipts = sorted((base / 'saved').glob('v*/processing.json'))
        if not saved_receipts:
            raise RuntimeError(f'{case}: missing saved receipt')
        receipt = json.loads(saved_receipts[-1].read_text())
        if receipt.get('missing_evidence') or receipt.get('passed') is not True:
            raise RuntimeError(f'{case}: saved evidence incomplete')
        proof.append({'case': case, 'offline': offline, 'compatibility': compat,
                      'saved': saved, 'saved_receipt': str(saved_receipts[-1].relative_to(ROOT)),
                      'saved_sha256': sha(saved_receipts[-1])})
        print(json.dumps({'case': case, 'passed': True}), flush=True)
    index = HERE / 'update902-short-primary-index.json'
    index.write_text(json.dumps({'manifest_sha256': sha(MANIFEST), 'proofs': proof}, indent=2) + '\n')
    print(json.dumps({'passed': len(proof), 'index_sha256': sha(index)}), flush=True)


if __name__ == '__main__':
    main()
