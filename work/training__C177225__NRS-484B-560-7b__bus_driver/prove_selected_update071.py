"""Prove all eight selected bus/officer chains against live JSON graph recipes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
INDEX = HERE / 'update071-selected-index.json'
OUT = ROOT / '.runtime-work/c177225-update071b'
PY = ROOT / '.venv-cpu/bin/python'
RUNTIME = ROOT / 'runtime.py'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, candidate, phase, args):
    log = HERE / f'update071-{case}-{candidate}-{phase}.log'
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(OUT / 'runtime')
    with log.open('w') as stream:
        result = subprocess.run([str(PY), str(RUNTIME), phase, *map(str, args)],
                                cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{case}/{candidate}/{phase}: exit {result.returncode}: {log}')
    return {'log': str(log.relative_to(ROOT)), 'sha256': sha(log)}


manifest = json.loads(MANIFEST.read_text())
manifest_sha = sha(MANIFEST)
index = {'manifest_sha256': manifest_sha, 'proofs': []}
if INDEX.exists():
    prior = json.loads(INDEX.read_text())
    if prior['manifest_sha256'] != manifest_sha:
        raise RuntimeError('Existing index belongs to another manifest')
    index = prior
done = {(item['case'], item['candidate']) for item in index['proofs']}
for entry in manifest['cases']:
    case_id = entry['case_id']
    case = case_id.removeprefix(HERE.name + '__')
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        if (case, candidate) in done:
            continue
        base = OUT / case / candidate
        selected_manifest = (HERE / f'update071-{case}-fallback1-manifest.json'
                             if candidate == 'fallback1' else MANIFEST)
        common = ['--manifest', selected_manifest, '--case', case_id]
        offline = run(case, candidate, 'offline', [*common, '--candidate', candidate,
                                                   '--output', base / 'offline'])
        compat = run(case, candidate, 'compatibility', [*common, '--candidate', candidate,
                                                        '--library', LIBRARY, '--validator', VALIDATOR,
                                                        '--output', base / 'compatibility'])
        saved = run(case, candidate, 'process-saved', [*common,
                                                       '--attempt', base / 'compatibility',
                                                       '--library', LIBRARY, '--validator', VALIDATOR,
                                                       '--output', base / 'saved'])
        receipt_path = base / 'saved/v0001/processing.json'
        receipt = json.loads(receipt_path.read_text())
        if receipt.get('passed') is not True or receipt.get('missing_evidence') is not False:
            raise RuntimeError(f'{case}/{candidate}: saved processing incomplete')
        index['proofs'].append({'case': case, 'candidate': candidate,
                                'selected_manifest_sha256': sha(selected_manifest),
                                'output_dir': str(base.relative_to(ROOT)), 'offline': offline,
                                'compatibility': compat, 'saved': saved,
                                'receipt_sha256': sha(receipt_path)})
        INDEX.write_text(json.dumps(index, indent=2) + '\n')
        print(json.dumps({'case': case, 'candidate': candidate, 'passed': True,
                          'total': len(index['proofs'])}), flush=True)
if len(index['proofs']) != 8:
    raise RuntimeError('Selected matrix count incomplete')
print(json.dumps({'passed': len(index['proofs']), 'index_sha256': sha(INDEX)}))
