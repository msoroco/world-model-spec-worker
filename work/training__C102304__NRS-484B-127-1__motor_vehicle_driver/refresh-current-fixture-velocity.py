"""Bind diagnostic trace velocity to source-joined Native body motion."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for condition in ('condition_a', 'condition_b'):
    folder = HERE/'current-fixture'/condition
    trace = folder/'trace.jsonl'
    samples = folder/'native_samples.jsonl'
    trace_rows = [json.loads(line) for line in trace.read_text().splitlines()]
    native_rows = [json.loads(line) for line in samples.read_text().splitlines()]
    if len(trace_rows) != 900 or len(native_rows) != 900:
        raise ValueError('Full 900-frame source interval required')
    for row, source in zip(trace_rows, native_rows):
        if row['frame'] != source['native_frame'] or row['time_s'] != source['time_s']:
            raise ValueError('Diagnostic trace and Native sample frame/time mismatch')
        ego = source['ego']
        if abs(row['speed_mps'] - ego['speed_mps']) > 1e-9:
            raise ValueError('Diagnostic trace and Native ego speed mismatch')
        forward = ego['native_forward_xy']
        row['velocity_mps'] = [ego['speed_mps']*forward[0], ego['speed_mps']*forward[1], 0.0]
    trace.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in trace_rows))
    capture_manifest = folder/'capture/manifest.json'
    capture = json.loads(capture_manifest.read_text())
    capture['sources']['trace.jsonl'] = sha(trace)
    capture_manifest.write_text(json.dumps(capture, indent=2, allow_nan=False) + '\n')
    recipe_path = HERE/'current-fixture'/(condition+'-recipe.json')
    recipe = json.loads(recipe_path.read_text())
    for source_path in (trace, capture_manifest):
        relative = source_path.relative_to(folder).as_posix()
        matches = [item for item in recipe['sources'] if item['path'] == relative]
        if len(matches) != 1 or REPO/matches[0]['source'] != source_path:
            raise ValueError('Recipe source binding differs for '+relative)
        matches[0]['sha256'] = sha(source_path)
    recipe_path.write_text(json.dumps(recipe, indent=2, allow_nan=False)+'\n')
    print(condition, sha(trace), sha(recipe_path))
