"""Rebind exact bus/officer diagnostic recipes to live adapter JSON graphs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2) + '\n')


def migrate(label, recipe_ref):
    recipe = json.loads((ROOT / recipe_ref).read_text())
    spec = json.loads((ROOT / recipe['generator']['source']).read_text())
    if len(spec['graphs']) != 600:
        raise ValueError('Expected 600 diagnostic graphs: ' + label)
    for graph in spec['graphs']:
        if not graph['path'].endswith('.pkl'):
            raise ValueError('Unexpected graph codec: ' + label)
        graph['path'] = graph['path'][:-4] + '.adapter.json'
    spec_path = HERE / f'update070-{label}-diagnostic-spec.json'
    save_new(spec_path, spec)
    recipe['generator'] = {'source': spec_path.relative_to(ROOT).as_posix(),
                           'sha256': sha(spec_path)}
    frame_sources = [item for item in recipe['sources']
                     if item['path'] == 'capture/native/frames.jsonl']
    if len(frame_sources) != 1:
        raise ValueError('Expected one frame-map source: ' + label)
    source = frame_sources[0]
    rows = [json.loads(line) for line in (ROOT / source['source']).read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 frame-map rows: ' + label)
    for row in rows:
        for key in ('base', 'abstract'):
            if key in row:
                if not row[key].endswith('.pkl'):
                    raise ValueError('Unexpected frame-map codec: ' + label)
                row[key] = row[key][:-4] + '.adapter.json'
        row['adapter_graph'] = row['base']
    frame_path = HERE / f'update070-{label}-frames.jsonl'
    if frame_path.exists():
        raise FileExistsError(frame_path)
    frame_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    source['source'] = frame_path.relative_to(ROOT).as_posix()
    source['sha256'] = sha(frame_path)
    recipe_path = HERE / f'update070-{label}-diagnostic-recipe.json'
    save_new(recipe_path, recipe)
    return recipe_path.relative_to(ROOT).as_posix()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    case = entry['case_id'].removeprefix(HERE.name + '__')
    entry['fixture_recipe'] = migrate(case, entry['fixture_recipe'])
    for candidate in entry['candidates']:
        if candidate.get('fixture_recipe'):
            candidate['fixture_recipe'] = migrate(case + '-' + candidate['id'],
                                                  candidate['fixture_recipe'])
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'recipes': 4, 'manifest_sha256': sha(MANIFEST)}))
