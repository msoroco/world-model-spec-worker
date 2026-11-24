"""Retained 30-second rail stop, right edge and two-queue diagnostics."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_rail_queue', ROOT / 'native' / 'measure_rail_queue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, ego_y, other_x):
    folder = ROOT / 'fixtures' / 'rail_queue' / name
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'geometry.json', {'rail_crossing_x_m': 0.0, 'right_highway_edge_y_m': 3.5,
                                   'total_marked_lanes': 2, 'vehicle_width_m': 1.8, 'vehicle_length_m': 4.5})
    gate = [{'frame': 1000 + i, 'time_s': i / 20, 'kind': 'rail_gate',
             'indication': 'stop' if 100 <= i < 400 else 'release'} for i in range(600)]
    actors = [{'frame': 1000 + i, 'time_s': i / 20,
               'actors': {'ego': {'x_m': -10.0, 'y_m': ego_y, 'speed_mps': 0.0},
                          'other': {'x_m': other_x, 'y_m': 2.0, 'speed_mps': 0.0}}} for i in range(600)]
    (folder / 'gate.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in gate))
    (folder / 'actors.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in actors))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_rail_stop_queue',
                                  'sha256': {n: module.digest(folder / n) for n in ('geometry.json', 'gate.jsonl', 'actors.jsonl')}})
    return folder


def edit_rows(folder, file, edit, rehash=True):
    path = folder / file
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    edit(rows)
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    if rehash:
        source = json.loads((folder / 'sources.json').read_text())
        source['sha256'][file] = module.digest(path)
        write(folder / 'sources.json', source)


def reject(folder, file, edit, expected, rehash=True):
    with tempfile.TemporaryDirectory() as scratch:
        trial = Path(scratch)
        for name in ('geometry.json', 'gate.jsonl', 'actors.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        edit_rows(trial, file, edit, rehash)
        try:
            module.measure(trial)
        except ValueError as error:
            assert expected in str(error), str(error)
            return str(error)
        raise AssertionError('Corrupt source was accepted')


observed, negatives = {}, {}
for name, ego_y, other_x in (('right_single_queue', 2.0, -16.0), ('left_single_queue', -1.0, -16.0),
                            ('left_abreast_queue', -1.0, -10.0)):
    folder = make(name, ego_y, other_x)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, 'actors.jsonl', lambda rows: rows[1]['actors']['ego'].update({'y_m': 0.0}), 'Source hash differs', False),
        'missing_other': reject(folder, 'actors.jsonl', lambda rows: rows[1]['actors'].pop('other'), 'Ego/other vehicle source missing'),
        'frame_gap': reject(folder, 'gate.jsonl', lambda rows: rows[1].update({'frame': 1010}), 'Native gate/actor frame join differs')}
assert all(v['stopped_during_gate_stop_frames'] == 300 for v in observed.values())
assert observed['right_single_queue']['minimum_right_edge_gap_m'] == 0.6
assert observed['left_single_queue']['minimum_right_edge_gap_m'] == 3.6
assert observed['left_abreast_queue']['abreast_two_queue_frames'] == 300
proof = {'format': 'c202463-rail-stop-queue-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'comparison_axes': ['ego lateral placement', 'other-vehicle longitudinal queue placement'],
         'limitations': ['synthetic gate does not establish independently supported stop duty',
                         'as far right as possible has no invented cutoff', 'two queue arrangements are measurements, not legal verdicts']}
path = ROOT / 'rail-queue-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 3, 'negatives': 9}, sort_keys=True))
