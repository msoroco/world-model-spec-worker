"""Retained 30-second two-approach-vehicle entry ordering diagnostic."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_private_entry', ROOT / 'native' / 'measure_private_entry.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, ego_arrival):
    folder = ROOT / 'fixtures' / 'private_entry' / name
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'geometry.json', {'private_way': 'y_negative_to_highway', 'highway': 'x_negative_to_positive',
                                   'conflict_x_m': 0.0, 'conflict_y_m': 0.0,
                                   'highway_vehicle_ids': ['approach_1', 'approach_2']})
    rows = []
    for i in range(600):
        rows.append({'frame': 1000 + i, 'time_s': i / 20,
                     'actors': {'ego': {'x_m': 0.0, 'y_m': (i - ego_arrival) * 0.1},
                                'approach_1': {'x_m': (i - 120) * 0.25, 'y_m': 0.0},
                                'approach_2': {'x_m': (i - 200) * 0.25, 'y_m': 0.0}}})
    (folder / 'actors.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_private_way_entry',
                                  'sha256': {n: module.digest(folder / n) for n in ('geometry.json', 'actors.jsonl')}})
    return folder


def edit_rows(folder, edit, rehash=True):
    path = folder / 'actors.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    edit(rows)
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    if rehash:
        source = json.loads((folder / 'sources.json').read_text())
        source['sha256']['actors.jsonl'] = module.digest(path)
        write(folder / 'sources.json', source)


def reject(folder, edit, expected, rehash=True):
    with tempfile.TemporaryDirectory() as scratch:
        trial = Path(scratch)
        for name in ('geometry.json', 'actors.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        edit_rows(trial, edit, rehash)
        try:
            module.measure(trial)
        except ValueError as error:
            assert expected in str(error), str(error)
            return str(error)
        raise AssertionError('Corrupt source was accepted')


observed, negatives = {}, {}
for name, arrival in (('yield_both', 240), ('enter_before_second', 160)):
    folder = make(name, arrival)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, lambda rows: rows[1]['actors']['ego'].update({'y_m': -1.0}), 'Source hash differs', False),
        'missing_approach': reject(folder, lambda rows: rows[1]['actors'].pop('approach_2'), 'Approaching vehicle source missing'),
        'frame_gap': reject(folder, lambda rows: rows[1].update({'frame': 1010}), 'Native frame/time join differs')}
assert observed['yield_both']['highway_vehicles_before_ego'] == 2
assert observed['enter_before_second']['highway_vehicles_before_ego'] == 1
assert observed['yield_both']['highway_arrival_frames'] == observed['enter_before_second']['highway_arrival_frames']
proof = {'format': 'c177626-private-entry-order-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'controlled_input': 'ego entry timing; two highway vehicle trajectories fixed',
         'limitations': ['synthetic trace is not Native motion', 'conflict arrival order is not full right-of-way judgment',
                         'every actually approaching vehicle must be inventoried in real capture']}
path = ROOT / 'private-entry-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
