"""Move the 14 selected short-case diagnostics to JSON adapter graphs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    count = 0
    for entry in manifest['cases']:
        recipe_ref = entry.get('fixture_recipe')
        if recipe_ref is None:
            continue
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        recipe = json.loads((ROOT / recipe_ref).read_text())
        old_source = recipe['generator']['source']
        spec = json.loads((ROOT / old_source).read_text())
        graphs = spec.get('graphs', [])
        if len(graphs) not in (240, 361):
            raise ValueError('Unexpected short diagnostic length')
        for graph in graphs:
            if not graph['path'].endswith('.pkl'):
                raise ValueError('Unexpected graph source')
            graph['path'] = graph['path'][:-4] + '.adapter.json'
        frame_path = 'capture/native/frames.jsonl'
        frames = [json.loads(line) for line in spec['files'][frame_path].splitlines()]
        if len(frames) != len(graphs):
            raise ValueError('Frame map count differs')
        for frame in frames:
            frame['base'] = frame['base'].replace('.pkl', '.adapter.json')
            if 'abstract' in frame:
                frame['abstract'] = frame['abstract'].replace('.pkl', '.adapter.json')
            frame['adapter_graph'] = frame['base']
        spec['files'][frame_path] = '\n'.join(json.dumps(frame) for frame in frames) + '\n'
        spec_path = HERE / f'update900-{suffix}-diagnostic.json'
        save(spec_path, spec)
        new_source = spec_path.relative_to(ROOT).as_posix()
        recipe['generator'] = {'source': new_source, 'sha256': sha(spec_path)}
        for source in recipe['sources']:
            if source['source'] == old_source:
                source['source'] = new_source
                source['sha256'] = sha(spec_path)
        recipe_path = HERE / f'update900-{suffix}-diagnostic-recipe.json'
        save(recipe_path, recipe)
        entry['fixture_recipe'] = recipe_path.relative_to(ROOT).as_posix()
        count += 1
        print(json.dumps({'case': suffix, 'frames': len(graphs), 'spec_sha256': sha(spec_path)}))
    if count != 14:
        raise ValueError('Selected short case count differs')
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'migrated_cases': count, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
