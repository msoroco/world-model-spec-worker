"""Derive synthetic trace velocity from retained Native speed and heading rows."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for suffix in ('probe_a', 'probe_b'):
    folder = HERE / f'current-v2-{suffix}-fixture'
    trace = folder / 'trace.jsonl'
    native = folder / 'native_samples.jsonl'
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    samples = [json.loads(line) for line in native.read_text().splitlines()]
    if len(rows) != 600 or len(samples) != 600:
        raise ValueError('Expected 600 joined source frames')
    for row, sample in zip(rows, samples):
        if row['frame'] != sample['native_frame'] or row['time_s'] != sample['time_s']:
            raise ValueError('Trace/Native frame join changed')
        if abs(row['speed_mps'] - sample['speed_mps']) > 1e-9:
            raise ValueError('Trace/Native speed changed')
        yaw = math.radians(sample['native_yaw_deg'])
        row['velocity_mps'] = [sample['speed_mps'] * math.cos(yaw),
                               sample['speed_mps'] * math.sin(yaw), 0.0]
    trace.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    capture = folder / 'capture/manifest.json'
    document = json.loads(capture.read_text())
    document['sources']['trace.jsonl'] = sha(trace)
    capture.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n')
    recipe_path = HERE / f'current-v2-{suffix}-fixture-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    for source_path in (trace, capture):
        matches = [item for item in recipe['sources']
                   if item['path'] == source_path.relative_to(folder).as_posix()]
        if len(matches) != 1 or ROOT / matches[0]['source'] != source_path:
            raise ValueError('Recipe source mismatch')
        matches[0]['sha256'] = sha(source_path)
    recipe_path.write_text(json.dumps(recipe, indent=2, allow_nan=False) + '\n')
    print(suffix, sha(trace), sha(recipe_path))
