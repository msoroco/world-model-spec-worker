"""Bind the directional approach's exact saved source and diagnostic recipe."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'directional-approach-experiment'
RUN = ROOT / '.runtime-work/c111662-directional-approach'
OFFLINE = RUN / 'offline-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, sort_keys=True) + '\n')


def main(suffix='reference'):
    if suffix not in ('reference', 'contrast'):
        raise ValueError('Only the intersection comparison pair is supported')
    offline = OFFLINE if suffix == 'reference' else RUN / 'contrast-offline'
    native = offline / 'work' / HERE.name / 'native'
    bundle = native / 'selected-draft' / suffix
    sys.path.insert(0, str(native))
    from saved import make_raw
    prefix = '' if suffix == 'reference' else suffix + '-'
    raw_path = DEST / (prefix + 'raw.json')
    write(raw_path, make_raw(bundle), compact=True)
    sys.path.pop(0)
    construction = json.loads((DEST / (prefix + 'construction.json')).read_text())
    road = next(row['content'] for row in construction['files'] if row['path'] == 'road.xodr')
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    source = HERE / 'current-16-experiment' / suffix / 'primary'
    diagnostic = json.loads((source / 'diagnostic.json').read_text())
    capture = json.loads(diagnostic['files']['capture/manifest.json'])
    capture['sources']['road.xodr'] = road_sha
    diagnostic['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    diagnostic_path = DEST / (prefix + 'diagnostic.json')
    write(diagnostic_path, diagnostic, compact=True)
    recipe = json.loads((source / 'recipe.json').read_text())
    diagnostic_ref = str(diagnostic_path.relative_to(ROOT))
    recipe['generator'] = {'source': diagnostic_ref, 'sha256': sha(diagnostic_path)}
    for row in recipe['sources']:
        if row['path'] == 'diagnostic-input.json':
            row.update(source=diagnostic_ref, sha256=sha(diagnostic_path))
        elif row['path'] == 'raw.json':
            row.update(source=str(raw_path.relative_to(ROOT)), sha256=sha(raw_path))
    recipe_path = DEST / (prefix + 'recipe.json')
    write(recipe_path, recipe)
    manifest_path = HERE / ('directional-approach-experiment-manifest.json' if suffix == 'reference'
                            else 'directional-approach-' + suffix + '-experiment-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'][0]['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
    write(manifest_path, manifest)
    print(json.dumps({'raw_sha256': sha(raw_path), 'diagnostic_sha256': sha(diagnostic_path),
                      'recipe_sha256': sha(recipe_path), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'reference')
