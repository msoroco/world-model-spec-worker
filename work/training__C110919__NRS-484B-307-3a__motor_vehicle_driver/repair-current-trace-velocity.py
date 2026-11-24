"""Bind synthetic trace velocity to retained Native sample speed and heading."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update(case):
    source = HERE / 'current-v2-source' / case
    native = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
    trace_path = source / 'trace.jsonl'
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    if len(native) != len(trace) or len(trace) != 600:
        raise ValueError('Native and trace frame counts differ')
    for sample, row in zip(native, trace):
        if sample['native_frame'] != row['frame'] or abs(sample['time_s'] - row['time_s']) > 1e-6:
            raise ValueError('Original frame join differs')
        if abs(sample['speed_mps'] - row['speed_mps']) > 1e-6 or abs(sample['native_yaw_deg'] - row['heading_deg']) > 1e-6:
            raise ValueError('Native speed or heading differs')
        yaw = math.radians(sample['native_yaw_deg'])
        row['velocity_mps'] = [sample['speed_mps'] * math.cos(yaw),
                               sample['speed_mps'] * math.sin(yaw), 0.0]
    trace_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in trace))
    capture_path = source / 'capture/manifest.json'
    capture = json.loads(capture_path.read_text())
    if capture.get('sources', {}).get('trace.jsonl') is None:
        raise ValueError('Capture manifest has no trace source')
    capture['sources']['trace.jsonl'] = sha(trace_path)
    capture_path.write_text(json.dumps(capture) + '\n')
    recipe_path = HERE / f'current-v2-{case}-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    for relative, target in [('trace.jsonl', trace_path), ('capture/manifest.json', capture_path)]:
        matches = [entry for entry in recipe['sources'] if entry['path'] == relative]
        if len(matches) != 1 or ROOT / matches[0]['source'] != target:
            raise ValueError('Recipe source differs: ' + relative)
        matches[0]['sha256'] = sha(target)
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': case, 'trace_sha256': sha(trace_path), 'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([update('witness_1'), update('witness_2')]))
