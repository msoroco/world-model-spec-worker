"""Migrate the two authored synthetic fixture recipes to the live JSON adapter."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def migrate(suffix):
    graph_spec = HERE / f'diagnostic-{suffix}.json'
    recipe_path = HERE / f'diagnostic-{suffix}-recipe.json'
    frame_path = HERE / 'diagnostic-sources' / suffix / 'capture/native/frames.jsonl'
    spec = json.loads(graph_spec.read_text())
    frames = [json.loads(line) for line in frame_path.read_text().splitlines()]
    if len(spec['graphs']) != len(frames) or len(frames) != 480:
        raise ValueError('Expected 480 frame-matched diagnostic graphs')
    for graph, frame in zip(spec['graphs'], frames):
        if graph['attributes']['frame'] != frame['frame']:
            raise ValueError('Graph and source frame identities differ')
        stem = f"graphs/base/{frame['frame']:08d}.adapter.json"
        graph['path'] = 'capture/native/' + stem
        frame.update(base=stem, abstract=stem, adapter_graph=stem,
                     nodes=len(graph['nodes']), edges=len(graph['edges']))
    write_json(graph_spec, spec)
    frame_path.write_text(''.join(json.dumps(frame, sort_keys=True) + '\n' for frame in frames))
    recipe = json.loads(recipe_path.read_text())
    recipe['generator']['sha256'] = sha(graph_spec)
    source = next(item for item in recipe['sources']
                  if item['path'] == 'capture/native/frames.jsonl')
    source['sha256'] = sha(frame_path)
    write_json(recipe_path, recipe)
    return {'suffix': suffix, 'graphs': len(frames),
            'generator_sha256': sha(graph_spec), 'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([migrate(suffix) for suffix in ('condition_a', 'condition_b')], indent=2))
