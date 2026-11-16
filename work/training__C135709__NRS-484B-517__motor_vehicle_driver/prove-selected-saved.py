"""Run actual pinned saved processing for all eight selected diagnostic captures."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
from worker_exchange.package_compatibility import materialize_case


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    rows = []
    for witness in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            case = ROOT.name+'__'+witness
            manifest = ROOT/('execution-manifest-'+witness+'-'+candidate+'-draft.json')
            recipe = ROOT/'selected-diagnostics'/witness/(candidate+'-recipe.json')
            base = REPO/'.runtime-work/update051-c135709-saved-all-v1'/witness/candidate
            fixture, attempt, output = (base/name for name in ('fixture', 'attempt', 'processed'))
            base.mkdir(parents=True, exist_ok=True)
            materialize(REPO, recipe, fixture)
            materialize_case(manifest, case, attempt, fixture, candidate)
            proof = ROOT/'update051-saved'/witness/candidate
            proof.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(REPO/'runtime.py'), 'process-saved',
                '--manifest', str(manifest), '--case', case,
                '--attempt', str(attempt), '--output', str(output),
                '--library', str(REPO/'runtime/pipeline/library'),
                '--validator', str(REPO/'.runtime-work/update051-decoder-current/.lake/build/bin/adapterCheck')]
            env = dict(os.environ, MPLCONFIGDIR='/tmp/c135709-mpl')
            with (proof/'command.log').open('w') as log:
                result = subprocess.run(command, cwd=REPO, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=300)
            row = {'case_id': case, 'candidate_id': candidate,
                'manifest_sha256': sha(manifest), 'recipe_sha256': sha(recipe),
                'command': ' '.join(command), 'exit_code': result.returncode,
                'log': (proof/'command.log').relative_to(ROOT).as_posix(),
                'log_sha256': sha(proof/'command.log')}
            if result.returncode == 0:
                receipt = output/'v0001/processing.json'
                shutil.copy2(receipt, proof/'processing.json')
                row['processing_sha256'] = sha(proof/'processing.json')
                data = json.loads(receipt.read_text())
                if (data.get('missing_evidence') is not False or
                    data.get('originals_preserved') is not True or
                    data.get('physical_acceptance_claimed') is not False or
                    data.get('legal_acceptance_claimed') is not False):
                    raise ValueError('Saved processing changed diagnostic provenance')
            rows.append(row)
            print(json.dumps({'case': witness, 'candidate': candidate,
                              'exit_code': result.returncode}), flush=True)
    matrix = {'format': 'c135709-current-selected-saved-matrix-v1',
        'results': rows, 'all_passed': all(row['exit_code'] == 0 for row in rows),
        'original_native_observed': False, 'delivery_ready': False}
    (ROOT/'update051-saved-matrix.json').write_text(json.dumps(matrix, indent=2)+'\n')
    if not matrix['all_passed']:
        raise ValueError('Selected saved processing failed; inspect exact logs')
    return matrix


if __name__ == '__main__':
    print(json.dumps({'passed': len(prove()['results'])}))
