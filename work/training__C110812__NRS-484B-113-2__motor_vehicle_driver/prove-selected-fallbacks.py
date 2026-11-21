"""Reprove final 42-second fallback bundles on the current CPU runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'runtime/pipeline'), str(ROOT / 'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.package_compatibility import materialize_case
from scenario_pipeline.worker_exchange.saved_processing import run

MANIFEST = HERE / 'selected-proof-manifest.json'
entries = json.loads(MANIFEST.read_text())['cases']
validator = ROOT / '.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


rows = []
for entry in entries:
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    for candidate in ('fallback1', 'fallback2', 'fallback3'):
        stem = f'selected-{suffix}-{candidate}'
        compat = ROOT / '.runtime-work' / ('c110812-' + stem + '-compatible')
        saved = ROOT / '.runtime-work' / ('c110812-' + stem + '-saved')
        log = HERE / (stem + '-compatibility.log')
        command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                   '--manifest', str(MANIFEST), '--case', case,
                   '--candidate', candidate, '--output', str(compat),
                   '--library', str(ROOT / 'runtime/pipeline/library'),
                   '--validator', str(validator)]
        with log.open('w') as output:
            status = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT).returncode
        if status:
            raise RuntimeError(f'{stem}: compatibility exit {status}: {log}')
        receipt = json.loads((compat / 'compatibility.json').read_text())
        if not receipt['passed'] or receipt['candidate_id'] != candidate:
            raise ValueError(f'{stem}: incorrect compatibility receipt')
        for source, target in (('compatibility.json', stem + '-compatibility-receipt.json'),
                               ('compatibility-analysis.log', stem + '-analysis.log'),
                               ('negative-analysis.log', stem + '-negative.log')):
            shutil.copyfile(compat / source, HERE / target)
        saved.mkdir(parents=True, exist_ok=False)
        source = materialize(ROOT, ROOT / entry['fixture_recipe'], saved / 'fixture')
        materialize_case(MANIFEST, case, saved / 'attempt', saved / 'fixture', candidate)
        result = run(MANIFEST, case, saved / 'attempt', saved / 'output',
                     ROOT / 'runtime/pipeline/library', validator)
        if not result.get('passed') or not result.get('recorded_only') or result.get('missing_evidence'):
            raise ValueError(f'{stem}: recorded-only saved proof failed')
        saved_receipt = HERE / (stem + '-saved-receipt.json')
        saved_receipt.write_text(json.dumps({'source': source, 'result': result}, indent=2) + '\n')
        row = {'case_id': case, 'candidate_id': candidate,
               'construction_sha256': next(c['construction_sha256'] for c in entry['candidates'] if c['id'] == candidate),
               'compatibility_receipt': stem + '-compatibility-receipt.json',
               'compatibility_sha256': sha(HERE / (stem + '-compatibility-receipt.json')),
               'saved_receipt': saved_receipt.name, 'saved_sha256': sha(saved_receipt),
               'recorded_only': True, 'physical_success_claimed': False}
        rows.append(row)
        (HERE / 'selected-fallback-summary.json').write_text(json.dumps({'rows': rows}, indent=2) + '\n')
        print(suffix, candidate, 'compatibility and recorded-only saved path passed', flush=True)
