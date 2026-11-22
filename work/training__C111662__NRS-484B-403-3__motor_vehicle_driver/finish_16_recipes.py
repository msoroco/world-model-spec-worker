"""Rebind 16 isolated exact candidate fixtures to current authored constructions."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / 'current-16-experiment'
RUN = ROOT / '.runtime-work/c111662-16'
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
POLICIES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, sort_keys=True) + '\n')


def main():
    base_manifest = json.loads((HERE / 'current-16-experiment-manifest.json').read_text())
    index = {}
    for suffix in CASES:
        entry = next(item for item in base_manifest['cases']
                     if item['case_id'].endswith('__' + suffix))
        for candidate in POLICIES:
            native = RUN / (suffix + '-' + candidate + '-offline') / 'work' / HERE.name / 'native'
            bundle = native / 'selected-draft' / suffix
            if not (bundle / 'config.json').is_file():
                raise ValueError('Materialize exact candidate first: ' + suffix + '/' + candidate)
            sys.path.insert(0, str(native))
            if suffix.startswith('divided_'):
                from saved_divided import make_raw
            else:
                from saved import make_raw
            variant = WORK / suffix / candidate
            raw_path = variant / 'raw.json'
            write(raw_path, make_raw(bundle), compact=True)
            sys.path.pop(0)
            for module_name in ('saved_divided', 'saved', 'divided_opening', 'build'):
                sys.modules.pop(module_name, None)
            selected_ref = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            construction = json.loads((HERE / selected_ref['construction']).read_text())
            road = next(item['content'] for item in construction['files']
                        if item['path'] == 'road.xodr')
            road_sha = hashlib.sha256(road.encode()).hexdigest()
            if candidate == 'primary':
                diagnostic_template = HERE / ('update500-' + suffix + '-diagnostic.json')
                recipe_template = HERE / ('update500-' + suffix + '-diagnostic-recipe.json')
            else:
                diagnostic_template = HERE / ('update015-selected-' + suffix + '-' + candidate + '-diagnostic.json')
                recipe_template = HERE / ('update043-current-fixtures/' + suffix + '/' + candidate + '/recipe.json')
            generator = json.loads(diagnostic_template.read_text())
            if candidate != 'primary':
                for graph in generator['graphs']:
                    path = graph['path']
                    if not path.endswith('.pkl'):
                        raise ValueError('Historical fallback graph path changed')
                    graph['path'] = path[:-4] + '.adapter.json'
                frames = []
                for line in generator['files']['capture/native/frames.jsonl'].splitlines():
                    row = json.loads(line)
                    if not row['base'].endswith('.pkl'):
                        raise ValueError('Historical fallback frame path changed')
                    row['base'] = row['base'][:-4] + '.adapter.json'
                    row['adapter_graph'] = row['base']
                    frames.append(json.dumps(row, separators=(',', ':'), sort_keys=True))
                generator['files']['capture/native/frames.jsonl'] = '\n'.join(frames) + '\n'
            capture = json.loads(generator['files']['capture/manifest.json'])
            capture['sources']['road.xodr'] = road_sha
            generator['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
            diagnostic_path = variant / 'diagnostic.json'
            write(diagnostic_path, generator, compact=True)
            if diagnostic_path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Diagnostic exceeds returned file limit: ' + suffix + '/' + candidate)
            recipe = json.loads(recipe_template.read_text())
            diagnostic_ref = str(diagnostic_path.relative_to(ROOT))
            recipe['generator'] = {'source': diagnostic_ref, 'sha256': sha(diagnostic_path)}
            for source in recipe['sources']:
                if source['path'] == 'diagnostic-input.json':
                    source.update(source=diagnostic_ref, sha256=sha(diagnostic_path))
                elif source['path'] == 'raw.json':
                    source.update(source=str(raw_path.relative_to(ROOT)), sha256=sha(raw_path))
            recipe_path = variant / 'recipe.json'
            write(recipe_path, recipe)
            manifest = json.loads((HERE / 'current-16-experiment-manifest.json').read_text())
            manifest['cases'] = [next(item for item in manifest['cases']
                                      if item['case_id'].endswith('__' + suffix))]
            manifest['cases'][0]['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
            manifest['status'] = 'isolated_current_runtime_exact_candidate_probe'
            manifest_path = HERE / ('current-16-manifest-' + suffix + '-' + candidate + '.json')
            write(manifest_path, manifest)
            index[suffix + '/' + candidate] = {
                'construction_sha256': selected_ref['construction_sha256'],
                'road_sha256': road_sha,
                'raw_sha256': sha(raw_path),
                'diagnostic_sha256': sha(diagnostic_path),
                'recipe_sha256': sha(recipe_path),
                'manifest_sha256': sha(manifest_path),
            }
    write(WORK / 'recipe-index.json', {
        'format': 'c111662-current-16-recipe-index-v1',
        'runtime_manifest_sha256': base_manifest['runtime_manifest_sha256'],
        'variants': index,
    })
    print(json.dumps({'variants': len(index), 'index_sha256': sha(WORK / 'recipe-index.json')}))


if __name__ == '__main__':
    main()
