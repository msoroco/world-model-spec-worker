"""Bind the isolated directional-junction probe to its materialized road."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'split-junction-experiment'
NATIVE = ROOT / '.runtime-work/c111662-split-junction/offline/work' / HERE.name / 'native'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, sort_keys=True) + '\n')


def main():
    if not (NATIVE / 'selected-draft/contrast/config.json').is_file():
        raise ValueError('Materialize the split-junction construction first')
    sys.path.insert(0, str(NATIVE))
    from saved import make_raw
    raw_path = WORK / 'raw.json'
    write(raw_path, make_raw(NATIVE / 'selected-draft/contrast'), compact=True)
    construction = json.loads((WORK / 'construction.json').read_text())
    road = next(item['content'] for item in construction['files'] if item['path'] == 'road.xodr')
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    generator = json.loads((HERE / 'update500-contrast-diagnostic.json').read_text())
    capture = json.loads(generator['files']['capture/manifest.json'])
    capture['sources']['road.xodr'] = road_sha
    generator['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    diagnostic_path = WORK / 'diagnostic.json'
    write(diagnostic_path, generator, compact=True)
    if diagnostic_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Diagnostic exceeds returned file limit')
    recipe = json.loads((HERE / 'update500-contrast-diagnostic-recipe.json').read_text())
    generator_ref = str(diagnostic_path.relative_to(ROOT))
    recipe['generator'] = {'source': generator_ref, 'sha256': sha(diagnostic_path)}
    for source in recipe['sources']:
        if source['path'] == 'diagnostic-input.json':
            source.update(source=generator_ref, sha256=sha(diagnostic_path))
        elif source['path'] == 'raw.json':
            source.update(source=str(raw_path.relative_to(ROOT)), sha256=sha(raw_path))
    recipe_path = WORK / 'recipe.json'
    write(recipe_path, recipe)
    manifest_path = HERE / 'split-junction-experiment-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'][0]['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
    write(manifest_path, manifest)
    print(json.dumps({'road_sha256': road_sha, 'diagnostic_sha256': sha(diagnostic_path),
                      'recipe_sha256': sha(recipe_path), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
