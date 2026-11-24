"""Create and prove retained textual roundabout lane diagnostics."""

import hashlib
import importlib.util
import json
import math
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_roundabout', ROOT / 'native' / 'measure_roundabout.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def generate(name, ego_radius):
    folder = ROOT / 'fixtures' / 'roundabout' / name
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / 'geometry.json', {
        'kind': 'synthetic_annular_roundabout',
        'outer_right_lane_radius_m': [13.0, 16.0],
        'inner_left_lane_radius_m': [10.0, 13.0],
        'direction': 'counterclockwise',
    })
    rows = []
    for i in range(600):
        angle = i * 3.0 / ego_radius / 20.0
        following_angle = angle - 0.1
        rows.append({
            'frame': 1000 + i, 'time_s': i / 20.0,
            'actors': {
                'ego': {'x_m': round(ego_radius * math.cos(angle), 9), 'y_m': round(ego_radius * math.sin(angle), 9), 'speed_mps': 3.0},
                'follower': {'x_m': round(ego_radius * math.cos(following_angle), 9), 'y_m': round(ego_radius * math.sin(following_angle), 9), 'speed_mps': 5.0},
            },
        })
    (folder / 'actors.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    write_json(folder / 'sources.json', {
        'kind': 'synthetic_cpu_roundabout_diagnostic',
        'sha256': {name: module.digest(folder / name) for name in ('geometry.json', 'actors.jsonl')},
    })
    return folder


def reject(folder, mutation, expected):
    with tempfile.TemporaryDirectory() as tmp:
        trial = Path(tmp)
        for name in ('geometry.json', 'actors.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        mutation(trial)
        try:
            module.measure(trial)
        except ValueError as error:
            if expected not in str(error):
                raise AssertionError(str(error)) from error
            return str(error)
        raise AssertionError('Corrupted source was accepted')


def mutate_source(folder):
    path = folder / 'actors.jsonl'
    path.write_text(path.read_text().replace('"speed_mps": 3.0', '"speed_mps": 2.0', 1))


def mutate_missing_follower(folder):
    path = folder / 'actors.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    rows[100]['actors'].pop('follower')
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    source = json.loads((folder / 'sources.json').read_text())
    source['sha256']['actors.jsonl'] = module.digest(path)
    write_json(folder / 'sources.json', source)


def mutate_frame_gap(folder):
    path = folder / 'actors.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    rows[100]['frame'] += 1
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    source = json.loads((folder / 'sources.json').read_text())
    source['sha256']['actors.jsonl'] = module.digest(path)
    write_json(folder / 'sources.json', source)


observed = {}
negatives = {}
for name, radius in (('extreme_right', 14.5), ('inner_left', 11.5)):
    folder = generate(name, radius)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, mutate_source, 'Source hash differs'),
        'missing_follower': reject(folder, mutate_missing_follower, 'Ego/follower source missing'),
        'frame_gap': reject(folder, mutate_frame_gap, 'Native frame/time join differs'),
    }
assert observed['extreme_right']['counts']['outer_right'] == 600
assert observed['inner_left']['counts']['inner_left'] == 600
for item in observed.values():
    assert item['counts']['follower_behind'] == 600
    assert item['counts']['ego_slower_than_follower'] == 600
proof = {
    'format': 'c132924-roundabout-lane-diagnostic-v1', 'selected': False, 'accepted': False,
    'observed': observed, 'negative_errors': negatives,
    'controlled_difference': 'ego and follower radial lane position, with shared speed and angle-time policy',
    'limitations': ['synthetic lane traces are not Native roundabout motion', 'slow speed plus following traffic does not settle legal impeding', 'passing necessity unproven'],
}
path = ROOT / 'roundabout-lane-proof.json'
write_json(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
