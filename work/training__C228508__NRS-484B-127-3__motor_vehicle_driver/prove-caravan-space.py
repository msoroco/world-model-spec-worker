"""Retained 30-second full group/combination extent diagnostic."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / '.runtime-work' / 'c228508-caravan-proofs'
SCRATCH.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('measure_caravan_space', ROOT / 'native' / 'measure_caravan_space.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def make(name, clear_gap):
    folder = ROOT / 'fixtures' / 'caravan' / name
    folder.mkdir(parents=True, exist_ok=True)
    lengths = {'lead': 4.5, 'ego_combination': 9.0, 'rear': 4.5}
    write(folder / 'composition.json', {'ordered_group': ['lead', 'ego_combination', 'rear'],
                                      'length_m': lengths, 'ego_tows_trailer': True, 'potential_entrant_length_m': 6.0})
    rows = []
    for i in range(600):
        lead = 100 + 6 * i / 20
        ego = lead - (lengths['lead'] + lengths['ego_combination']) / 2 - clear_gap
        rear = ego - (lengths['ego_combination'] + lengths['rear']) / 2 - clear_gap
        rows.append({'frame': 1000 + i, 'time_s': i / 20,
                     'actors': {'lead': {'x_m': lead, 'speed_mps': 6.0},
                                'ego_combination': {'x_m': ego, 'speed_mps': 6.0},
                                'rear': {'x_m': rear, 'speed_mps': 6.0},
                                'potential_entrant': {'x_m': ego, 'speed_mps': 6.0, 'y_m': 3.5}}})
    (folder / 'actors.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    write(folder / 'sources.json', {'kind': 'synthetic_cpu_caravan_space',
                                  'sha256': {n: module.digest(folder / n) for n in ('composition.json', 'actors.jsonl')}})
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
    with tempfile.TemporaryDirectory(dir=SCRATCH) as scratch:
        trial = Path(scratch)
        for name in ('composition.json', 'actors.jsonl', 'sources.json'):
            (trial / name).write_bytes((folder / name).read_bytes())
        edit_rows(trial, edit, rehash)
        try:
            module.measure(trial)
        except ValueError as error:
            assert expected in str(error), str(error)
            return str(error)
        raise AssertionError('Corrupt source was accepted')


observed, negatives = {}, {}
for name, gap in (('wide', 30.0), ('narrow', 8.0)):
    folder = make(name, gap)
    observed[name] = module.measure(folder)
    negatives[name] = {
        'changed_hash': reject(folder, lambda rows: rows[1]['actors']['rear'].update({'x_m': 0.0}), 'Source hash differs', False),
        'missing_group_member': reject(folder, lambda rows: rows[1]['actors'].pop('rear'), 'Complete group/entrant source missing'),
        'frame_gap': reject(folder, lambda rows: rows[1].update({'frame': 1010}), 'Native frame/time join differs')}
assert observed['wide']['minimum_clear_gap_m'] == {'lead_to_ego_combination': 30.0, 'ego_combination_to_rear': 30.0}
assert observed['narrow']['minimum_clear_gap_m'] == {'lead_to_ego_combination': 8.0, 'ego_combination_to_rear': 8.0}
proof = {'format': 'c228508-caravan-combination-space-diagnostic-v1', 'selected': False, 'accepted': False,
         'observed': observed, 'negative_errors': negatives,
         'controlled_input': 'both consecutive clear spaces; group speed, combination extents and entrant length fixed',
         'limitations': ['synthetic traces are not Native towing or entry', 'caravan membership and legal region require independent support',
                         'static length surplus is not sufficient space or without-danger judgment']}
path = ROOT / 'caravan-space-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': module.digest(path), 'positives': 2, 'negatives': 6}, sort_keys=True))
