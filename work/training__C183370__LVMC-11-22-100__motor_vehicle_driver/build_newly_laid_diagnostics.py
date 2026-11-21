"""Rebind source-shaped CPU fixtures to the newly laid alternative pair.

These are synthetic software-path inputs. Their map/actor rows and short-form
pixel content cannot establish real surface age, warning, or physical outcome.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CASES = {'newly_laid_crossing': 'reference',
         'newly_laid_avoidance': 'contrast'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows = []
    for case, old in CASES.items():
        old_path = HERE / 'selected-diagnostics' / old / 'primary.json'
        source = json.loads(old_path.read_text())
        files = source['files']
        readback = json.loads(files['live-readback.json'])
        plan = readback['plan']
        plan['laid_polygon_xy_m'] = plan.pop('repair_polygon_xy_m')
        plan['cases'] = {
            suffix: {'requested_pavement_crossing': suffix == 'newly_laid_crossing'}
            for suffix in CASES}
        plan['newly_laid_status_verified'] = False
        readback['newly_laid_status_verified'] = False
        files['live-readback.json'] = json.dumps(readback, indent=2, sort_keys=True) + '\n'
        receipt = json.loads(files['capture-receipt.json'])
        receipt['case'] = case
        receipt['newly_laid_status_verified'] = False
        files['capture-receipt.json'] = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
        folder = HERE / 'newly-laid-diagnostics' / case
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'primary.json'
        recipe_path = folder / 'primary-recipe.json'
        if path.exists() or recipe_path.exists():
            raise ValueError('Preserve previous newly laid diagnostic source')
        path.write_text(json.dumps(source, separators=(',', ':')) + '\n')
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Newly laid diagnostic source exceeds return limit')
        relative = 'work/' + ASSIGNMENT + '/newly-laid-diagnostics/' + case + '/primary.json'
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-source.json', 'source': relative,
                               'sha256': sha(path)}],
                  'generator': {'source': relative, 'sha256': sha(path)}}
        recipe_path.write_text(json.dumps(recipe, indent=2, sort_keys=True) + '\n')
        rows.append({'case_id': ASSIGNMENT + '__' + case,
                     'source': relative, 'source_sha256': sha(path),
                     'recipe': str(recipe_path.relative_to(HERE)),
                     'recipe_sha256': sha(recipe_path),
                     'synthetic_fixture': True})
    result = {'format': 'c183370-newly-laid-diagnostic-source-bindings-v1',
              'cases': rows, 'original_native_observed': False,
              'physical_or_legal_acceptance_claimed': False}
    path = HERE / 'update138-newly-laid-diagnostic-bindings.json'
    if path.exists():
        raise ValueError('Preserve previous newly laid diagnostic binding')
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'cases': len(rows), 'bindings_sha256': sha(path)},
                     sort_keys=True))


if __name__ == '__main__':
    build()
