"""Retained 30-second taxi standing/sign-hours diagnostic."""

import importlib.util
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_yellow_zone', ROOT / 'native' / 'measure_yellow_zone.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, hour):
    folder = ROOT / 'fixtures' / 'yellow_zone' / name
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'zone.json', {'curb_color': 'yellow', 'x_range_m': [0.0, 20.0], 'y_range_m': [-1.0, 1.0]})
    write(folder / 'sign.json', {'kind': 'synthetic_posted_condition', 'start_local': '09:00', 'end_local': '17:00',
                               'purpose': 'taxicab passenger waiting', 'timezone': 'America/Los_Angeles'})
    start = datetime(2026, 11, 23, hour)
    rows = [{'frame': 1000 + i, 'time_s': i / 20,
             'civil_time_local': (start + timedelta(seconds=i / 20)).isoformat(timespec='milliseconds'),
             'actor_kind': 'taxicab', 'x_m': 10.0, 'y_m': 0.0, 'speed_mps': 0.0} for i in range(600)]
    (folder / 'taxi.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_yellow_curb',
                                  'sha256': {n: module.digest(folder / n) for n in ('zone.json', 'sign.json', 'taxi.jsonl')}})
    return folder


def edit_rows(folder, edit, rehash=True):
    path = folder / 'taxi.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    edit(rows)
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    if rehash:
        source = json.loads((folder / 'sources.json').read_text())
        source['sha256']['taxi.jsonl'] = module.digest(path)
        write(folder / 'sources.json', source)


def reject(folder, edit, expected, rehash=True):
    with tempfile.TemporaryDirectory() as scratch:
        trial = Path(scratch)
        for name in ('zone.json', 'sign.json', 'taxi.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        edit_rows(trial, edit, rehash)
        try:
            module.measure(trial)
        except ValueError as error:
            assert expected in str(error), str(error)
            return str(error)
        raise AssertionError('Corrupt source was accepted')


observed, negatives = {}, {}
for name, hour in (('within_posted_hours', 10), ('outside_posted_hours', 18)):
    folder = make(name, hour)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, lambda rows: rows[1].update({'x_m': 11.0}), 'Source hash differs', False),
        'missing_taxi': reject(folder, lambda rows: rows[1].pop('actor_kind'), 'Taxicab source missing'),
        'civil_time_gap': reject(folder, lambda rows: rows[1].update({'civil_time_local': '2026-11-23T12:00:00.000'}), 'Civil time join differs')}
assert observed['within_posted_hours']['sign_active_standing_frames'] == 600
assert observed['outside_posted_hours']['sign_active_standing_frames'] == 0
assert all(v['standing_in_yellow_zone_frames'] == 600 for v in observed.values())
proof = {'format': 'c150173-yellow-zone-hours-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'controlled_input': 'civil clock hour; taxi stop, zone and authored sign fixed',
         'limitations': ['synthetic sign not verified authoritative', 'passenger waiting purpose not observed',
                         'outside posted hours does not itself establish prohibition']}
path = ROOT / 'yellow-zone-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
