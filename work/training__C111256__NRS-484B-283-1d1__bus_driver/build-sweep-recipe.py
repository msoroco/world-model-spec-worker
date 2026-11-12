"""Create a source-hashed synthetic saved-source recipe for sweep diagnostics."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import inspect


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((HERE / 'update015-reference-diagnostic.json').read_text())
    rows = [json.loads(line) for line in source['files']['native_samples.jsonl'].splitlines()]
    if len(rows) != 480 or any(row.get('speed_provenance') != 'synthetic_native_sample' for row in rows):
        raise ValueError('Base diagnostic Native source differs')
    for index, row in enumerate(rows):
        row['controller_request'] = {'hold_requested': index == 100}
    source['files']['native_samples.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    spec = HERE / 'update028-sweep-diagnostic.json'
    spec.write_text(json.dumps(source, separators=(',', ':')) + '\n')
    if spec.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic specification exceeds worker return limit')
    relative = spec.relative_to(REPO).as_posix()
    digest = sha(spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': relative, 'sha256': digest}],
              'generator': {'source': relative, 'sha256': digest}}
    path = HERE / 'update028-sweep-recipe.json'
    path.write_text(json.dumps(recipe, indent=2) + '\n')
    inspect(REPO, path)
    print(json.dumps({'spec_sha256': digest, 'recipe_sha256': sha(path),
                      'synthetic_native_rows': len(rows),
                      'source_hash_verified': True, 'original_recordings_accepted': 0},
                     sort_keys=True))


if __name__ == '__main__':
    main()
