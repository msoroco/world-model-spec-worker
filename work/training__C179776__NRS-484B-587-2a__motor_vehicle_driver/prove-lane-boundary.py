"""Retained 30-second controlled-access lane/shoulder diagnostics."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_lane_boundary', ROOT / 'native' / 'measure_lane_boundary.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, shoulder):
    folder = ROOT / 'fixtures' / 'lane_boundary' / name
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'geometry.json', {'controlled_access': True, 'marked_lanes_y_m': [[-4.0, 0.0], [0.0, 4.0]],
                                   'paved_shoulder_y_m': [4.0, 6.0], 'ego_width_m': 1.8})
    rows = [{'frame': 1000 + i, 'time_s': i / 20, 'actor_kind': 'ordinary_motor_vehicle',
             'x_m': i * 0.2, 'y_m': 5.0 if shoulder and i >= 200 else 2.5} for i in range(600)]
    (folder / 'ego.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_controlled_access_lane',
                                  'sha256': {n: module.digest(folder / n) for n in ('geometry.json', 'ego.jsonl')}})
    return folder


def edit_rows(folder, edit, rehash=True):
    path = folder / 'ego.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    edit(rows)
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    if rehash:
        source = json.loads((folder / 'sources.json').read_text())
        source['sha256']['ego.jsonl'] = module.digest(path)
        write(folder / 'sources.json', source)


def reject(folder, edit, expected, rehash=True):
    with tempfile.TemporaryDirectory() as scratch:
        trial = Path(scratch)
        for name in ('geometry.json', 'ego.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        edit_rows(trial, edit, rehash)
        try:
            module.measure(trial)
        except ValueError as error:
            assert expected in str(error), str(error)
            return str(error)
        raise AssertionError('Corrupt source was accepted')


observed, negatives = {}, {}
for name, shoulder in (('marked_lane', False), ('paved_shoulder', True)):
    folder = make(name, shoulder)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, lambda rows: rows[1].update({'y_m': 2.6}), 'Source hash differs', False),
        'missing_vehicle': reject(folder, lambda rows: rows[1].pop('actor_kind'), 'Vehicle source missing'),
        'frame_gap': reject(folder, lambda rows: rows[1].update({'frame': 1010}), 'Native frame/time join differs')}
assert observed['marked_lane']['footprint_outside_marked_lanes_frames'] == 0
assert observed['paved_shoulder']['footprint_outside_marked_lanes_frames'] == 400
assert observed['paved_shoulder']['footprint_fully_on_paved_shoulder_frames'] == 400
proof = {'format': 'c179776-controlled-access-lane-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'controlled_input': 'ego lateral route; controlled-access geometry and longitudinal motion fixed',
         'limitations': ['synthetic trace is not Native motion', 'emergency and subsection 3 authorization unresolved',
                         'special-vehicle/sign shoulder exception unresolved']}
path = ROOT / 'lane-boundary-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
