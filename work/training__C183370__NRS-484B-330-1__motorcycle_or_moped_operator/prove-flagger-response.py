"""Retained 30-second flagger signal and motorcycle response diagnostics."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('measure_flagger_response', ROOT / 'native' / 'measure_flagger_response.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, hold):
    folder = ROOT / 'fixtures' / 'flagger' / name
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / 'zone.json', {'kind': 'marked_temporary_traffic_control', 'stop_line_x_m': 0.0,
                               'approach': 'x_negative_to_positive', 'signal_governs_approach': True})
    signals, vehicles = [], []
    for i in range(600):
        signals.append({'frame': 1000 + i, 'time_s': i / 20, 'role': 'flagger',
                        'governs_ego': True, 'indication': 'stop' if 100 <= i < 300 else 'release'})
        x = (-10 + i * 0.05) if i < 100 else ((-5.0 if i <= 300 else -5 + (i - 300) * 0.1) if hold else -5 + (i - 100) * 0.05)
        speed = 1.0 if i < 100 or not hold else (0.0 if i <= 300 else 2.0)
        vehicles.append({'frame': 1000 + i, 'time_s': i / 20, 'actor_kind': 'motorcycle_or_moped',
                         'x_m': x, 'speed_mps': speed})
    (folder / 'signal.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in signals))
    (folder / 'ego.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in vehicles))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_flagger_stop',
                                  'sha256': {n: module.digest(folder / n) for n in ('zone.json', 'signal.jsonl', 'ego.jsonl')}})
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
        for name in ('zone.json', 'signal.jsonl', 'ego.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        edit_rows(trial, file, edit, rehash)
        try:
            module.measure(trial)
        except ValueError as error:
            assert expected in str(error), str(error)
            return str(error)
        raise AssertionError('Corrupt source was accepted')


observed, negatives = {}, {}
for name, hold in (('hold_until_release', True), ('cross_during_stop', False)):
    folder = make(name, hold)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, 'ego.jsonl', lambda rows: rows[1].update({'x_m': -8.0}), 'Source hash differs', False),
        'missing_flagger': reject(folder, 'signal.jsonl', lambda rows: rows[1].pop('role'), 'Governing flagger source missing'),
        'frame_gap': reject(folder, 'signal.jsonl', lambda rows: rows[1].update({'frame': 1010}), 'Native signal/ego frame join differs')}
assert observed['hold_until_release']['indication_at_crossing'] == 'release'
assert observed['cross_during_stop']['indication_at_crossing'] == 'stop'
assert observed['hold_until_release']['first_stop_frame'] == observed['cross_during_stop']['first_stop_frame']
proof = {'format': 'c183370-flagger-response-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'controlled_input': 'motorcycle response controller; governing signal and marked-zone definition fixed',
         'limitations': ['synthetic signal is not verified authorized or visible', 'marked-zone designation is authored only',
                         'trace is not Native motorcycle motion']}
path = ROOT / 'flagger-response-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
