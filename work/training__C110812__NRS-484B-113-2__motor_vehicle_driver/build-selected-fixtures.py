"""Extend the existing stationary tail to the 840-frame delivery timing contract."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = 'work/' + HERE.name + '/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extend_rows(raw):
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != 480:
        raise ValueError('Expected 480-frame source fixture')
    for index in range(480, 840):
        row = copy.deepcopy(rows[-1])
        frame, time_s = 100 + index, round((index + 1) / 20, 8)
        for key in ('frame', 'native_frame', 'carla_frame', 'original_frame', 'replay_frame'):
            if key in row:
                row[key] = frame
        if 'video_frame' in row:
            row['video_frame'] = index
        for key in ('time_s', 'simulation_time', 'recording_time_s', 'replay_simulation_time_s'):
            if key in row:
                row[key] = time_s
        for key in ('base', 'abstract', 'adapter_graph'):
            if key in row:
                row[key] = f'graphs/base/{frame:08d}.adapter.json'
        rows.append(row)
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


for suffix in ('condition_a', 'condition_b'):
    source = json.loads((HERE / f'diagnostic-{suffix}.json').read_text())
    for path in tuple(source['files']):
        if path.endswith('.jsonl'):
            source['files'][path] = extend_rows(source['files'][path])
    capture = json.loads(source['files']['capture/manifest.json'])
    capture['frames'] = 840
    capture['sources']['trace.jsonl'] = hashlib.sha256(source['files']['trace.jsonl'].encode()).hexdigest()
    source['files']['capture/manifest.json'] = json.dumps(capture, separators=(',', ':'))
    if len(source['graphs']) != 480:
        raise ValueError('Expected 480 graph markers')
    for index in range(480, 840):
        frame = 100 + index
        graph = copy.deepcopy(source['graphs'][-1])
        graph['path'] = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        graph['attributes']['frame'] = frame
        source['graphs'].append(graph)
    for video in source['videos']:
        video['frames'] = 840
    spec = HERE / f'selected-diagnostic-{suffix}.json'
    spec.write_text(json.dumps(source, separators=(',', ':')) + '\n')
    assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input-assignment.json',
                           'source': 'inputs/' + HERE.name + '/assignment.json',
                           'sha256': sha(assignment)}],
              'generator': {'source': BASE + spec.name, 'sha256': sha(spec)}}
    (HERE / f'selected-diagnostic-{suffix}-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    print(suffix, spec.stat().st_size, sha(spec))

manifest_path = HERE / 'selected-proof-manifest.json'
manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    suffix = 'condition_a' if entry['case_id'].endswith('__false') else 'condition_b'
    entry['fixture_recipe'] = BASE + f'selected-diagnostic-{suffix}-recipe.json'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
