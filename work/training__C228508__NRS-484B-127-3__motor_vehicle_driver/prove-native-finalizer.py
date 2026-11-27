"""Source-shaped saved measurement and damaging mutation proof, CPU only."""

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / 'native'
sys.path.insert(0, str(NATIVE))
from engineering import commanded_centers, CANDIDATES
from finalize import measure
SCRATCH = ROOT.parents[1] / '.runtime-work' / 'c228508-finalizer'
SCRATCH.mkdir(parents=True, exist_ok=True)
AID = 'training__C228508__NRS-484B-127-3__motor_vehicle_driver'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def rectangle(x, y, half_length):
    return [[x - half_length, y - 1], [x - half_length, y + 1],
            [x + half_length, y + 1], [x + half_length, y - 1]]


def build(folder, suffix, candidate):
    case_id = AID + '__' + suffix
    context = {'case_id': case_id, 'candidate_id': candidate,
               'public_highway_status_verified': False,
               'outside_business_district_verified': False,
               'caravan_membership_verified': False,
               'trailer_coupling_verified': False}
    write(folder / 'authored-context.json', context)
    rows = []
    for index in range(600):
        centers = commanded_centers(suffix, candidate, index)
        actors = {}
        for name in ('lead', 'ego_combination', 'trailer_proxy', 'rear', 'potential_entrant'):
            x = (centers['ego_combination'] + 2.25 if name == 'ego_combination'
                 else centers['ego_combination'] - 2.25 if name == 'trailer_proxy'
                 else centers[name])
            y = -5.25 if name == 'potential_entrant' else -1.75
            half = 3.0 if name == 'potential_entrant' else 2.25
            actors[name] = {'native_road_id': 1, 'native_lane_id': (-2 if index < 120 else -1) if name == 'potential_entrant' else -1,
                            'native_body_xy_m': rectangle(x, y, half),
                            'native_center_xy_m': [x, y],
                            'native_velocity_xy_mps': [CANDIDATES[candidate], 0],
                            'speed_mps': CANDIDATES[candidate]}
        rows.append({'native_frame': 1000 + index, 'time_s': (index + 1) / 20,
                     'actors': actors, 'requested_group_speed_mps': CANDIDATES[candidate]})
    (folder / 'native_samples.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    bind(folder, case_id, candidate)


def bind(folder, case_id, candidate):
    write(folder / 'source-manifest.json', {
        'format': 'c228508-original-native-draft-sources-v1',
        'case_id': case_id, 'candidate_id': candidate,
        'sha256': {name: digest(folder / name) for name in ('authored-context.json', 'native_samples.jsonl')}})


def mutate_rows(folder, mutation):
    path = folder / 'native_samples.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mutation(rows)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


observed = {}
for suffix in ('probe_a', 'probe_b'):
    for candidate in ('primary', 'fallback1'):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as name:
            folder = Path(name)
            build(folder, suffix, candidate)
            observed[suffix + '-' + candidate] = measure(folder)
assert observed['probe_a-primary']['minimum_clear_space_m'] == {
    'lead_to_combination_m': 30.0, 'combination_to_rear_m': 30.0}
assert observed['probe_b-primary']['minimum_clear_space_m'] == {
    'lead_to_combination_m': 8.0, 'combination_to_rear_m': 8.0}
assert all(not v['legal_verdict_claimed'] and not v['trailer_coupling_verified'] for v in observed.values())
assert all(v['entrant_transition_observed'] for v in observed.values())
assert all(v['all_caravan_actors_forward_frames'] == 600 for v in observed.values())

negative = {}
with tempfile.TemporaryDirectory(dir=SCRATCH) as name:
    folder = Path(name)
    build(folder, 'probe_a', 'primary')
    mutate_rows(folder, lambda rows: rows[1]['actors'].pop('rear'))
    try:
        measure(folder)
    except ValueError as error:
        assert 'source hash differs' in str(error)
        negative['unbound_source_edit'] = str(error)
    else:
        raise AssertionError('Unbound original source edit accepted')

mutations = {
    'missing_rear': (lambda rows: rows[1]['actors'].pop('rear'), 'complete caravan actor inventory'),
    'wrong_lane': (lambda rows: rows[1]['actors']['trailer_proxy'].update({'native_lane_id': -2}), 'lane/road identity'),
    'entrant_left_corridor': (lambda rows: rows[1]['actors']['potential_entrant'].update({'native_lane_id': -3}), 'lane/road identity'),
    'reversed_caravan_actor': (lambda rows: rows[1]['actors']['rear'].update({'native_velocity_xy_mps': [-2, 0]}), 'reversed direction'),
    'frame_gap': (lambda rows: rows[1].update({'native_frame': 9999}), 'frame/time join'),
    'body_overlap': (lambda rows: rows[1]['actors']['lead'].update({'native_body_xy_m': rectangle(rows[1]['actors']['ego_combination']['native_center_xy_m'][0], -1.75, 2.25)}), 'overlap or reverse'),
    'missing_body_corner': (lambda rows: rows[1]['actors']['rear'].update({'native_body_xy_m': []}), 'four-corner actor body'),
    'short_capture': (lambda rows: rows.pop(), '600-frame Native window'),
}
for label, (mutation, expected) in mutations.items():
    with tempfile.TemporaryDirectory(dir=SCRATCH) as name:
        folder = Path(name)
        build(folder, 'probe_a', 'primary')
        mutate_rows(folder, mutation)
        bind(folder, AID + '__probe_a', 'primary')
        try:
            measure(folder)
        except ValueError as error:
            assert expected in str(error), (label, str(error))
            negative[label] = str(error)
        else:
            raise AssertionError('Rebound damaging source accepted: ' + label)

proof = {'format': 'c228508-source-bound-draft-finalizer-proof-v1',
         'finalizer_sha256': digest(NATIVE / 'finalize.py'),
         'four_candidate_paths': observed, 'damaging_source_rejections': negative,
         'selected_delivery_claimed': False, 'native_execution_claimed': False,
         'limitations': ['Source-shaped rows are synthetic, not Native recording',
                         'No camera, trailer coupling, caravan membership, legal region or entry-safety verification']}
path = ROOT / 'native-finalizer-proof.json'
write(path, proof)
print(json.dumps({'proof_sha256': digest(path), 'positives': len(observed), 'negatives': len(negative)}))
