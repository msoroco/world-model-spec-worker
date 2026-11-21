"""Run current-runtime compatibility and recorded-only CPU proofs for the control."""
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

MANIFEST = HERE / 'control-proof-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__control'))
    case = entry['case_id']
    rows = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        stem = 'current-base-control-' + candidate
        compat = ROOT / '.runtime-work' / ('c110812-' + stem + '-compatible')
        saved = ROOT / '.runtime-work' / ('c110812-' + stem + '-saved')
        proof = HERE / (stem + '-compatibility-receipt.json')
        saved_proof = HERE / (stem + '-saved-receipt.json')
        if not proof.is_file():
            cmd = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                   '--manifest', str(MANIFEST), '--case', case, '--candidate', candidate,
                   '--output', str(compat), '--library', str(ROOT / 'runtime/pipeline/library'),
                   '--validator', str(VALIDATOR)]
            log = HERE / (stem + '-compatibility.log')
            with log.open('w') as output:
                status = subprocess.run(cmd, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT).returncode
            if status:
                raise RuntimeError(f'{stem}: compatibility exit {status}; see {log}')
            for source, target in (('compatibility.json', proof),
                                   ('compatibility-analysis.log', HERE / (stem + '-analysis.log')),
                                   ('negative-analysis.log', HERE / (stem + '-negative.log'))):
                shutil.copyfile(compat / source, target)
        receipt = json.loads(proof.read_text())
        selected = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id'] == candidate)
        if (not receipt['passed'] or receipt['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']
                or receipt['construction_sha256'] != selected['construction_sha256']
                or receipt['candidate_id'] != candidate):
            raise ValueError('Control compatibility binding differs: ' + stem)
        if not saved_proof.is_file():
            saved.mkdir(parents=True, exist_ok=False)
            source = materialize(ROOT, ROOT / entry['fixture_recipe'], saved / 'fixture')
            materialize_case(MANIFEST, case, saved / 'attempt', saved / 'fixture', candidate)
            result = run(MANIFEST, case, saved / 'attempt', saved / 'output',
                         ROOT / 'runtime/pipeline/library', VALIDATOR)
            if (not result.get('passed') or not result.get('recorded_only')
                    or result.get('missing_evidence')
                    or result['analysis_revision']['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
                raise ValueError('Control saved processing differs: ' + stem)
            saved_proof.write_text(json.dumps({'source': source, 'result': result}, indent=2) + '\n')
        result = json.loads(saved_proof.read_text())['result']
        if result['candidate_id'] != candidate or result['analysis_revision']['construction_sha256'] != selected['construction_sha256']:
            raise ValueError('Control saved receipt changed: ' + stem)
        rows.append({'case_id': case, 'candidate_id': candidate,
                     'construction_sha256': selected['construction_sha256'],
                     'compatibility_receipt': proof.name, 'compatibility_sha256': sha(proof),
                     'saved_receipt': saved_proof.name, 'saved_sha256': sha(saved_proof),
                     'recorded_only': True, 'physical_success_claimed': False})
        (HERE / 'current-base-control-matrix-summary.json').write_text(
            json.dumps({'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                        'rows': rows}, indent=2) + '\n')
        print(candidate, 'control compatibility and saved-only passed', flush=True)


if __name__ == '__main__':
    main()
