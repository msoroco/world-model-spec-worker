"""Retained 30-second bicycle response diagnostic with source negatives."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_rider_response', ROOT / 'native' / 'measure_rider_response.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, close):
    folder = ROOT / 'fixtures' / 'rider' / name
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'geometry.json', {'ego_width_m': 1.8, 'rider_width_m': 0.6, 'rider_type': 'bicycle'})
    rows = []
    for i in range(600):
        rows.append({'frame': 1000 + i, 'time_s': i / 20,
                     'actors': {'ego': {'y_m': 2.0 if close and i >= 200 else 0.0, 'speed_mps': 4.0},
                                'rider': {'y_m': 2.8, 'speed_mps': 2.0 if close and i >= 220 else 4.0}}})
    (folder / 'actors.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_rider_response',
                                  'sha256': {n: module.digest(folder / n) for n in ('geometry.json', 'actors.jsonl')}})
    return folder


def reject(folder, mutation, error_text):
    with tempfile.TemporaryDirectory() as scratch:
        trial = Path(scratch)
        for name in ('geometry.json', 'actors.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        mutation(trial)
        try:
            module.measure(trial)
        except ValueError as error:
            assert error_text in str(error), str(error)
            return str(error)
        raise AssertionError('Corrupted source was accepted')


def edit_rows(folder, transform, rehash=True):
    path = folder / 'actors.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    transform(rows)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    if rehash:
        source = json.loads((folder / 'sources.json').read_text())
        source['sha256']['actors.jsonl'] = module.digest(path)
        write(folder / 'sources.json', source)


def changed_hash(folder):
    edit_rows(folder, lambda rows: rows[1]['actors']['ego'].update({'speed_mps': 3.0}), False)


def missing_rider(folder):
    edit_rows(folder, lambda rows: rows[1]['actors'].pop('rider'))


def frame_gap(folder):
    edit_rows(folder, lambda rows: rows[1].update({'frame': 1010}))


observed, negatives = {}, {}
for name, close in (('clearance', False), ('lateral_intrusion', True)):
    folder = make(name, close)
    observed[name] = module.measure(folder)
    negatives[name] = {'changed_hash': reject(folder, changed_hash, 'Source hash differs'),
                       'missing_rider': reject(folder, missing_rider, 'Ego/rider source missing'),
                       'frame_gap': reject(folder, frame_gap, 'Native frame/time join differs')}
assert observed['clearance']['near_frames'] == 0
assert observed['lateral_intrusion']['near_frames'] == 400
assert observed['lateral_intrusion']['first_ego_lateral_change_frame'] == 1200
assert observed['lateral_intrusion']['first_rider_speed_drop_frame'] == 1220
proof = {'format': 'c136495-rider-response-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'controlled_input': 'synthetic ego lateral trajectory; rider brake response is scripted and does not prove causation',
         'limitations': ['lawful rider status unverified', 'driver intent unverified', 'scripted response is not physical Native behavior']}
path = ROOT / 'rider-response-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
