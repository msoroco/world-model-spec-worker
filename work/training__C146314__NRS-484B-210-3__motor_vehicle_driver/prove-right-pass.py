"""Retained 30-second paved/right-shoulder pass diagnostic."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_right_pass', ROOT / 'native' / 'measure_right_pass.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, shoulder):
    folder = ROOT / 'fixtures' / 'right_pass' / name
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'geometry.json', {'paved_y_m': [-4.0, 4.0], 'right_shoulder_y_m': [4.0, 6.0],
                                   'right_shoulder_paved': False, 'ego_width_m': 1.8,
                                   'ego_length_m': 4.5, 'lead_length_m': 4.5})
    rows = []
    for i in range(600):
        rows.append({'frame': 1000 + i, 'time_s': i / 20,
                     'actors': {'ego': {'x_m': i * 0.1, 'y_m': 4.2 if shoulder and 300 <= i <= 500 else 2.5},
                                'lead': {'x_m': 20 + i * 0.05, 'y_m': 0.5}}})
    (folder / 'actors.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_right_pass',
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
for name, shoulder in (('paved', False), ('unpaved_shoulder', True)):
    folder = make(name, shoulder)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, lambda rows: rows[1]['actors']['ego'].update({'y_m': 2.6}), 'Source hash differs', False),
        'missing_lead': reject(folder, lambda rows: rows[1]['actors'].pop('lead'), 'Ego/lead source missing'),
        'frame_gap': reject(folder, lambda rows: rows[1].update({'frame': 1010}), 'Native frame/time join differs')}
assert observed['paved']['right_pass_and_off_paved_frames'] == 0
assert observed['unpaved_shoulder']['right_pass_and_off_paved_frames'] > 0
assert observed['paved']['right_pass_overlap_frames'] == observed['unpaved_shoulder']['right_pass_overlap_frames']
proof = {'format': 'c146314-right-pass-footprint-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'controlled_input': 'ego lateral route onto unpaved right shoulder during otherwise fixed right-pass timing',
         'limitations': ['synthetic trace is not Native motion', 'footprint excursion does not prove that leaving pavement was required',
                         'accepted membership lacks source-hashed equivalence']}
path = ROOT / 'right-pass-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
