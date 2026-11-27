"""Run source-bound public compatibility for all current probe candidates."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
MANIFEST = FOLDER / 'execution-probe-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c229597-library-current/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(item):
    case, candidate, construction_sha = item
    suffix = case.removeprefix(FOLDER.name + '__')
    scratch = ROOT / '.runtime-work' / ('c394566-public-v17-' + suffix + '-' + candidate)
    existing = scratch / 'compatibility.json'
    if scratch.exists() and not existing.is_file():
        raise ValueError('Incomplete public scratch requires repair: ' + str(scratch))
    command = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(ROOT / 'runtime.py'), 'compatibility',
               '--manifest', str(MANIFEST), '--case', case, '--candidate', candidate,
               '--output', str(scratch), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch))
    if existing.is_file():
        prior = json.loads(existing.read_text())
        recipe = FOLDER / ('fixture-recipe-' + suffix + '.json')
        if (prior.get('passed') is not True or prior.get('construction_sha256') != construction_sha
                or prior.get('fixture_recipe_sha256') != sha(recipe)):
            raise ValueError('Stale public scratch requires repair: ' + str(scratch))
    else:
        completed = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, timeout=600)
        if completed.returncode:
            raise ValueError('Public compatibility failed for ' + suffix + '/' + candidate + ': ' + completed.stdout[-1500:])
    target_dir = FOLDER / 'compatibility'
    target_dir.mkdir(parents=True, exist_ok=True)
    source_names = [('compatibility.json', 'compatibility.json'),
                    ('compatibility-analysis.log', 'analysis.log'),
                    ('negative-analysis.log', 'negative.log')]
    files = {}
    for source, suffix_name in source_names:
        target = target_dir / (suffix + '-' + candidate + '-' + suffix_name)
        shutil.copyfile(scratch / source, target)
        files[source] = {'path': str(target.relative_to(FOLDER)), 'sha256': sha(target)}
    receipt = json.loads((scratch / 'compatibility.json').read_text())
    if receipt.get('passed') is not True or receipt.get('construction_sha256') != construction_sha:
        raise ValueError('Public receipt mismatch for ' + suffix + '/' + candidate)
    return case, candidate, files


def main():
    manifest = json.loads(MANIFEST.read_text())
    items = []
    for entry in manifest['cases']:
        items.append((entry['case_id'], 'primary', entry['construction_sha256']))
        items.extend((entry['case_id'], c['id'], c['construction_sha256']) for c in entry['candidates'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        proofs = list(pool.map(run, items))
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    for case, candidate, files in proofs:
        entry = by_case[case] if candidate == 'primary' else next(
            c for c in by_case[case]['candidates'] if c['id'] == candidate)
        entry['compatibility'] = {'receipt': files['compatibility.json']['path'],
                                  'sha256': files['compatibility.json']['sha256'],
                                  'log': files['compatibility-analysis.log']['path'],
                                  'negative_log': files['negative-analysis.log']['path']}
        if candidate == 'primary':
            entry['negative'] = {'log': files['negative-analysis.log']['path']}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'public_checks': len(proofs)}))


if __name__ == '__main__':
    main()
