"""Reprove migrated-input exact roundabout candidates on the pinned CPU runtime."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as output:
        process = subprocess.run(command, cwd=ROOT, stdout=output,
                                 stderr=subprocess.STDOUT, timeout=1200)
    if process.returncode:
        raise ValueError(f'CPU command failed ({process.returncode}): {log}')


def main(case, candidate):
    proof = HERE / 'update048-proof' / case / candidate
    proof.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / 'update048-execution-manifest.json').read_text())
    case_id = AID + '__' + case
    entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
    if candidate != 'primary':
        historical = json.loads((HERE / f'execution-manifest-{case}-{candidate}.json').read_text())
        entry['fixture_recipe'] = next(e['fixture_recipe'] for e in historical['cases']
                                       if e['case_id'] == case_id)
    recipe = ROOT / entry['fixture_recipe']
    if not recipe.is_file():
        raise ValueError('Missing candidate-specific textual fixture recipe')
    mini = HERE / f'update048-manifest-{case}-{candidate}.json'
    mini.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    output = ROOT / '.runtime-work/update048-c132497' / case / candidate
    py = sys.executable
    common = ['--manifest', str(mini), '--case', case_id,
              '--library', 'runtime/pipeline/library',
              '--validator', '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck']
    run([py, 'runtime.py', 'offline', '--manifest', str(mini), '--case', case_id,
         '--candidate', candidate, '--output', str(output / 'offline'), '--python', py],
        proof / 'offline.log')
    run([py, 'runtime.py', 'compatibility', *common, '--candidate', candidate,
         '--output', str(output / 'compat')], proof / 'compat.log')
    run([py, 'runtime.py', 'process-saved', *common, '--attempt', str(output / 'compat'),
         '--output', str(output / 'saved')], proof / 'saved.log')
    for source, name in ((output / 'compat/compatibility.json', 'compatibility.json'),
                         (output / 'compat/compatibility-analysis.log', 'analysis.log'),
                         (output / 'compat/negative-analysis.log', 'negative-analysis.log'),
                         (output / 'saved/v0001/processing.json', 'processing.json')):
        shutil.copyfile(source, proof / name)
    compatibility = json.loads((proof / 'compatibility.json').read_text())
    processing = json.loads((proof / 'processing.json').read_text())
    selected = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
    if (not compatibility['passed'] or not processing['passed'] or
            compatibility['construction_sha256'] != selected['construction_sha256'] or
            processing['native_revision']['construction_sha256'] != selected['construction_sha256'] or
            compatibility['fixture_recipe_sha256'] != sha(recipe)):
        raise ValueError('Current-input candidate receipt differs')
    print(json.dumps({'case': case, 'candidate': candidate, 'passed': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    args = parser.parse_args()
    main(args.case, args.candidate)
