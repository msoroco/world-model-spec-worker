"""Reprove inventory-corrected selected bundles with unchanged source-hashed raw data."""
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
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log):
    with log.open('w') as stream:
        result = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                check=False, timeout=1200)
    if result.returncode:
        raise ValueError(f'CPU proof exited {result.returncode}: {log}')


def main(case, candidate):
    proof = HERE / 'update046b-proof' / case / candidate
    proof.mkdir(parents=True, exist_ok=True)
    base = json.loads((HERE / 'update046-execution-manifest.json').read_text())
    case_id = AID + '__' + case
    entry = next(e for e in base['cases'] if e['case_id'] == case_id)
    selected = entry if candidate == 'primary' else next(e for e in entry['candidates'] if e['id'] == candidate)
    bundle = json.loads((HERE / selected['construction']).read_text())
    raw = (HERE / 'update043c-current-reference-primary-raw.json'
           if (case, candidate) == ('reference', 'primary')
           else HERE / 'update043-current-fixtures' / case / candidate / 'raw.json')
    recipe = (HERE / 'update043c-current-reference-primary-recipe.json'
              if (case, candidate) == ('reference', 'primary')
              else HERE / 'update043-current-fixtures' / case / candidate / 'recipe.json')
    nested = next(item['content'] for item in bundle['files']
                  if item['path'].endswith(f'/selected-draft/{case}/config.json'))
    if hashlib.sha256(nested.encode()).hexdigest() != json.loads(raw.read_text())['config_sha256']:
        raise ValueError('Raw source no longer matches nested candidate config')
    recipe_data = json.loads(recipe.read_text())
    source = next(x for x in recipe_data['sources'] if x['path'] == 'raw.json')
    if source['sha256'] != sha(raw):
        raise ValueError('Recipe no longer binds candidate raw source')
    entry['fixture_recipe'] = str(recipe.relative_to(ROOT))
    mini = HERE / f'update046b-manifest-{case}-{candidate}.json'
    mini.write_text(json.dumps(base, indent=2, ensure_ascii=False) + '\n')
    output = ROOT / '.runtime-work/update046b-c111662' / case / candidate
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
    if (not compatibility['passed'] or not processing['passed'] or
            compatibility['construction_sha256'] != selected['construction_sha256']):
        raise ValueError('Current inventory package proof differs')
    print(json.dumps({'case': case, 'candidate': candidate, 'passed': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    args = parser.parse_args()
    main(args.case, args.candidate)
