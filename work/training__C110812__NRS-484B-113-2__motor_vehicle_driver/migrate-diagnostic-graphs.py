"""Rebind existing synthetic graph fixtures to the live JSON adapter format."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for suffix in ('condition_a', 'condition_b'):
    spec_path = HERE / f'diagnostic-{suffix}.json'
    recipe_path = HERE / f'diagnostic-{suffix}-recipe.json'
    spec = json.loads(spec_path.read_text())
    frames = [json.loads(line) for line in spec['files']['capture/native/frames.jsonl'].splitlines()]
    if len(frames) != 480 or len(spec['graphs']) != len(frames):
        raise ValueError('Expected 480 matched synthetic frames and graphs')
    for frame, graph in zip(frames, spec['graphs']):
        if frame['frame'] != graph['attributes']['frame']:
            raise ValueError('Frame and graph differ')
        stem = f"graphs/base/{frame['frame']:08d}.adapter.json"
        frame.update(base=stem, abstract=stem, adapter_graph=stem,
                     nodes=len(graph['nodes']), edges=len(graph['edges']))
        graph['path'] = 'capture/native/' + stem
    spec['files']['capture/native/frames.jsonl'] = ''.join(
        json.dumps(frame, sort_keys=True) + '\n' for frame in frames)
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    recipe = json.loads(recipe_path.read_text())
    recipe['generator']['sha256'] = sha(spec_path)
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, len(frames), sha(spec_path), sha(recipe_path))
