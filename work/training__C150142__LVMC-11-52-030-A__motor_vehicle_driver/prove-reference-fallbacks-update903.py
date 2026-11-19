"""Prove three current-runtime reference fallback chains without CARLA."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
CASE = HERE.name + '__reference'
OUT = ROOT / '.runtime-work/c150142-update903/reference'
PY = ROOT / '.venv-cpu/bin/python'
RUNTIME = ROOT / 'runtime.py'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(candidate, phase, args):
    log = HERE / f'update903-reference-{candidate}-{phase}.log'
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(OUT / 'runtime')
    with log.open('w') as stream:
        result = subprocess.run([str(PY), str(RUNTIME), phase, *map(str, args)],
                                cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{candidate} {phase}: exit {result.returncode}: {log}')
    return {'log': str(log.relative_to(ROOT)), 'sha256': sha(log)}


proofs = []
for candidate in ('fallback1', 'fallback2', 'fallback3'):
    base = OUT / candidate
    common = ['--manifest', MANIFEST, '--case', CASE]
    offline = run(candidate, 'offline', [*common, '--candidate', candidate,
                                         '--output', base / 'offline'])
    compat = run(candidate, 'compatibility', [*common, '--candidate', candidate,
                                              '--library', LIBRARY, '--validator', VALIDATOR,
                                              '--output', base / 'compatibility'])
    saved = run(candidate, 'process-saved', [*common, '--attempt', base / 'compatibility',
                                             '--library', LIBRARY, '--validator', VALIDATOR,
                                             '--output', base / 'saved'])
    receipt_path = base / 'saved/v0001/processing.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('passed') is not True or receipt.get('missing_evidence') is not False:
        raise RuntimeError(candidate + ': saved processing incomplete')
    proofs.append({'candidate': candidate, 'offline': offline, 'compatibility': compat,
                   'saved': saved, 'receipt_sha256': sha(receipt_path)})
    print(json.dumps({'candidate': candidate, 'passed': True}), flush=True)
index = HERE / 'update903-reference-fallback-index.json'
index.write_text(json.dumps({'manifest_sha256': sha(MANIFEST), 'proofs': proofs}, indent=2) + '\n')
print(json.dumps({'passed': len(proofs), 'index_sha256': sha(index)}))
