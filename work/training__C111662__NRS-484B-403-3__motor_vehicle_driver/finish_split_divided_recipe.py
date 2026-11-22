"""Bind isolated divided primaries to the split carriageway road and raw rows."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'split-divided-experiment'
RUN = ROOT / '.runtime-work/c111662-split-divided'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, sort_keys=True) + '\n')


def main():
    manifest_path = HERE / 'split-divided-experiment-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        native = RUN / ('offline-' + suffix + '-v2') / 'work' / HERE.name / 'native'
        selected = native / 'selected-draft' / suffix
        if not (selected / 'config.json').is_file():
            raise ValueError('Materialize split divided construction first: ' + suffix)
        sys.path.insert(0, str(native))
        from saved_divided import make_raw
        raw_path = WORK / (suffix + '-raw.json')
        write(raw_path, make_raw(selected), compact=True)
        sys.path.pop(0)
        for module_name in ('saved_divided', 'saved', 'divided_opening', 'build'):
            sys.modules.pop(module_name, None)
        construction = json.loads((HERE / entry['construction']).read_text())
        road = next(item['content'] for item in construction['files'] if item['path'] == 'road.xodr')
        road_sha = hashlib.sha256(road.encode()).hexdigest()
        generator = json.loads((HERE / ('update500-' + suffix + '-diagnostic.json')).read_text())
        capture = json.loads(generator['files']['capture/manifest.json'])
        capture['sources']['road.xodr'] = road_sha
        generator['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
        diagnostic_path = WORK / (suffix + '-diagnostic.json')
        write(diagnostic_path, generator, compact=True)
        if diagnostic_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Diagnostic exceeds returned file limit')
        recipe = json.loads((HERE / ('update500-' + suffix + '-diagnostic-recipe.json')).read_text())
        source_path = str(diagnostic_path.relative_to(ROOT))
        recipe['generator'] = {'source': source_path, 'sha256': sha(diagnostic_path)}
        for source in recipe['sources']:
            if source['path'] == 'diagnostic-input.json':
                source.update(source=source_path, sha256=sha(diagnostic_path))
            elif source['path'] == 'raw.json':
                source.update(source=str(raw_path.relative_to(ROOT)), sha256=sha(raw_path))
        recipe_path = WORK / (suffix + '-recipe.json')
        write(recipe_path, recipe)
        entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
        proof[suffix] = {'road_sha256': road_sha, 'diagnostic_sha256': sha(diagnostic_path),
                         'recipe_sha256': sha(recipe_path)}
    write(manifest_path, manifest)
    print(json.dumps({'cases': proof, 'manifest_sha256': sha(manifest_path)}, sort_keys=True))


if __name__ == '__main__':
    main()
