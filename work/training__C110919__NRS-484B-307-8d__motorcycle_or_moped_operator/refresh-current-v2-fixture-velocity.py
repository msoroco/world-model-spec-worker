"""Bind synthetic trace velocity to the retained Native speed and heading rows."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for condition in ('condition_a', 'condition_b'):
    folder = HERE / f'current-v2-{condition}-fixture'
    trace = folder / 'trace.jsonl'
    samples = folder / 'native_samples.jsonl'
    trace_rows = [json.loads(line) for line in trace.read_text().splitlines()]
    native_rows = [json.loads(line) for line in samples.read_text().splitlines()]
    if len(trace_rows) != 600 or len(native_rows) != 600:
        raise ValueError('Expected 600 source rows')
    for row, source in zip(trace_rows, native_rows):
        if row['frame'] != source['native_frame'] or row['time_s'] != source['time_s']:
            raise ValueError('Trace/Native source frame mismatch')
        if abs(row['speed_mps'] - source['speed_mps']) > 1e-9:
            raise ValueError('Trace/Native speed mismatch')
        yaw = math.radians(source['native_yaw_deg'])
        row['velocity_mps'] = [
            source['speed_mps'] * math.cos(yaw),
            source['speed_mps'] * math.sin(yaw),
            0.0,
        ]
    trace.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in trace_rows))
    capture_manifest = folder / 'capture/manifest.json'
    capture = json.loads(capture_manifest.read_text())
    capture['sources']['trace.jsonl'] = sha(trace)
    capture_manifest.write_text(json.dumps(capture, indent=2, allow_nan=False) + '\n')
    recipe = HERE / f'current-v2-{condition}-fixture-recipe.json'
    document = json.loads(recipe.read_text())
    for source_path in (trace, capture_manifest):
        matching = [item for item in document['sources']
                    if item['path'] == source_path.relative_to(folder).as_posix()]
        if len(matching) != 1 or ROOT / matching[0]['source'] != source_path:
            raise ValueError('Fixture recipe source mismatch')
        matching[0]['sha256'] = sha(source_path)
    recipe.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n')
    print(condition, sha(trace), sha(recipe))
