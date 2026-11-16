"""Run current pinned Core/video compatibility for eight selected candidates."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = json.loads((ROOT/'execution-manifest-draft.json').read_text())
VALIDATOR = REPO/'.runtime-work/update051-decoder-current/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    if not VALIDATOR.is_file():
        raise ValueError('Build the current pinned decoder first')
    results = []
    for witness in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            manifest = json.loads(json.dumps(BASE))
            entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__'+witness))
            entry['fixture_recipe'] = ('work/'+ROOT.name+
                '/selected-diagnostics/'+witness+'/'+candidate+'-recipe.json')
            manifest_path = ROOT/('execution-manifest-'+witness+'-'+candidate+'-draft.json')
            manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
            output = REPO/'.runtime-work/update051-c135709-compat-all-v1'/witness/candidate
            proof = ROOT/'update051-proof'/witness/candidate
            proof.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(REPO/'runtime.py'), 'compatibility',
                '--manifest', str(manifest_path), '--case', entry['case_id'],
                '--candidate', candidate, '--output', str(output),
                '--library', str(REPO/'runtime/pipeline/library'),
                '--validator', str(VALIDATOR)]
            env = dict(os.environ, MPLCONFIGDIR='/tmp/c135709-mpl')
            with (proof/'command.log').open('w') as log:
                result = subprocess.run(command, cwd=REPO, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=300)
            row = {'case_id': entry['case_id'], 'candidate_id': candidate,
                'manifest': manifest_path.relative_to(ROOT).as_posix(),
                'manifest_sha256': sha(manifest_path),
                'fixture_recipe': entry['fixture_recipe'],
                'fixture_recipe_sha256': sha(REPO/entry['fixture_recipe']),
                'command': ' '.join(command), 'exit_code': result.returncode,
                'log': (proof/'command.log').relative_to(ROOT).as_posix(),
                'log_sha256': sha(proof/'command.log')}
            if result.returncode == 0:
                for name, target in (('compatibility.json', 'receipt.json'),
                                     ('compatibility-analysis.log', 'analysis.log'),
                                     ('negative-analysis.log', 'negative.log')):
                    shutil.copy2(output/name, proof/target)
                    row[target+'_sha256'] = sha(proof/target)
                receipt = json.loads((proof/'receipt.json').read_text())
                if (receipt.get('passed') is not True or
                    receipt.get('candidate_id') != candidate or
                    receipt.get('case_id') != entry['case_id'] or
                    receipt.get('fixture_recipe_sha256') != row['fixture_recipe_sha256']):
                    raise ValueError('Pinned compatibility receipt mismatches exact candidate')
            results.append(row)
            print(json.dumps({'case': witness, 'candidate': candidate,
                              'exit_code': result.returncode}), flush=True)
    matrix = {'format': 'c135709-current-selected-compatibility-matrix-v1',
        'results': results, 'all_passed': all(r['exit_code'] == 0 for r in results),
        'original_native_observed': False, 'delivery_ready': False}
    (ROOT/'update051-proof-matrix.json').write_text(json.dumps(matrix, indent=2)+'\n')
    if not matrix['all_passed']:
        raise ValueError('Some selected compatibility checks failed; inspect exact logs')
    return matrix


if __name__ == '__main__':
    print(json.dumps({'passed': len(prove()['results'])}))
