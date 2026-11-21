"""Reprove all exact 42-second candidates on the currently pinned base runtime."""
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

MANIFEST = HERE / 'current-base-proof-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = json.loads(MANIFEST.read_text())['cases']
    pinned = json.loads(MANIFEST.read_text())['runtime_manifest_sha256']
    rows = []
    for entry in entries:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            stem = f'current-base-{suffix}-{candidate}'
            compat = ROOT / '.runtime-work' / ('c110812-' + stem + '-compatible')
            saved = ROOT / '.runtime-work' / ('c110812-' + stem + '-saved')
            receipt_path = HERE / (stem + '-compatibility-receipt.json')
            saved_path = HERE / (stem + '-saved-receipt.json')
            if suffix == 'true' and candidate == 'primary':
                receipt_path = HERE / 'current-base-compatible-true-primary-receipt.json'
                saved_path = HERE / 'current-base-saved-true-primary-receipt.json'
            if not receipt_path.is_file():
                command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                           '--manifest', str(MANIFEST), '--case', case, '--candidate', candidate,
                           '--output', str(compat), '--library', str(ROOT / 'runtime/pipeline/library'),
                           '--validator', str(VALIDATOR)]
                log = HERE / (stem + '-compatibility.log')
                with log.open('w') as output:
                    status = subprocess.run(command, cwd=ROOT, stdout=output,
                                            stderr=subprocess.STDOUT).returncode
                if status:
                    raise RuntimeError(f'{stem}: compatibility exit {status}; see {log}')
                for source, target in (('compatibility.json', receipt_path),
                                       ('compatibility-analysis.log', HERE / (stem + '-analysis.log')),
                                       ('negative-analysis.log', HERE / (stem + '-negative.log'))):
                    shutil.copyfile(compat / source, target)
            receipt = json.loads(receipt_path.read_text())
            expected = entry['construction_sha256'] if candidate == 'primary' else next(
                c['construction_sha256'] for c in entry['candidates'] if c['id'] == candidate)
            if (not receipt['passed'] or receipt['runtime_manifest_sha256'] != pinned
                    or receipt['construction_sha256'] != expected or receipt['candidate_id'] != candidate):
                raise ValueError('Current base compatibility binding differs: ' + stem)
            if not saved_path.is_file():
                saved.mkdir(parents=True, exist_ok=False)
                source = materialize(ROOT, ROOT / entry['fixture_recipe'], saved / 'fixture')
                materialize_case(MANIFEST, case, saved / 'attempt', saved / 'fixture', candidate)
                result = run(MANIFEST, case, saved / 'attempt', saved / 'output',
                             ROOT / 'runtime/pipeline/library', VALIDATOR)
                if (not result.get('passed') or not result.get('recorded_only')
                        or result.get('missing_evidence')
                        or result['analysis_revision']['runtime_manifest_sha256'] != pinned):
                    raise ValueError('Current base saved proof differs: ' + stem)
                saved_path.write_text(json.dumps({'source': source, 'result': result}, indent=2) + '\n')
            saved_receipt = json.loads(saved_path.read_text())
            if (saved_receipt['result']['analysis_revision']['runtime_manifest_sha256'] != pinned
                    or saved_receipt['result']['candidate_id'] != candidate):
                raise ValueError('Current base saved receipt differs: ' + stem)
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': expected, 'compatibility_receipt': receipt_path.name,
                         'compatibility_sha256': sha(receipt_path), 'saved_receipt': saved_path.name,
                         'saved_sha256': sha(saved_path), 'recorded_only': True,
                         'physical_success_claimed': False})
            (HERE / 'current-base-matrix-summary.json').write_text(
                json.dumps({'runtime_manifest_sha256': pinned, 'rows': rows}, indent=2) + '\n')
            print(suffix, candidate, 'current-base compatibility and saved-only passed', flush=True)


if __name__ == '__main__':
    main()
