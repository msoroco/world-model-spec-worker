"""Audit the same-map two-cycle motorcycle contrast from saved source rows."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    manifest = read(HERE / 'execution-manifest.json')
    if len(manifest['cases']) != 2:
        raise ValueError('Selected comparison needs two exact cases')
    pair = {}
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        if condition not in ('condition_a', 'condition_b'):
            raise ValueError('Unexpected selected condition')
        folder = HERE / 'current-v2-candidates' / condition / 'primary'
        saved = read(folder / 'saved-proof.json')
        receipt = saved['processing']
        if (saved['construction_sha256'] != entry['construction_sha256']
                or receipt['candidate_id'] != 'primary'
                or receipt['originals_preserved'] is not True
                or receipt['recorded_only'] is not True):
            raise ValueError('Saved primary construction is not bound')
        attempt = ROOT / f'.runtime-work/c110919-owner104-rebind/saved-{condition}-primary/attempt'
        source = rows(attempt / 'native_samples.jsonl')
        mapping = rows(attempt / 'video_frames.jsonl')
        if len(source) != len(mapping) or len(source) != 600 or any(
                row['native_frame'] != frame['carla_frame'] or abs(row['time_s'] - frame['time_s']) > 1e-8
                for row, frame in zip(source, mapping)):
            raise ValueError('Saved source frame join differs')
        if any(str(row['signal_state_observed']).casefold() != 'red' for row in source):
            raise ValueError('Ego red was not held')
        if any(row['turn_prohibition_present'] or row['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja'
               for row in source):
            raise ValueError('Selected motorcycle or authored device context changed')
        turn = next((index for index, row in enumerate(source) if row['ego_turn_entered']), None)
        if turn is None:
            raise ValueError('No source-observed right turn')
        source_hashes = {name: sha(attempt / name) for name in
                         ('road.xodr', 'road_geometry.json', 'native_samples.jsonl',
                          'body_history.jsonl', 'video_frames.jsonl')}
        if any(receipt['original_source_hashes'].get(name) != digest
               for name, digest in source_hashes.items()):
            raise ValueError('Saved source hash changed')
        pair[condition] = {'turn_index': turn,
                           'cycles_at_turn': source[turn]['complete_cross_signal_cycles'],
                           'road_sha256': source_hashes['road.xodr'],
                           'road_geometry_sha256': source_hashes['road_geometry.json'],
                           'source_sha256': source_hashes['native_samples.jsonl'],
                           'saved_proof_sha256': sha(folder / 'saved-proof.json'),
                           'compatibility_sha256': sha(folder / 'compatibility.json'),
                           'pedestrian_conflict_frames': [i for i, row in enumerate(source)
                                                           if row['walker_conflict_occupied']],
                           'traffic_conflict_frames': [i for i, row in enumerate(source)
                                                        if row['cross_traffic_conflict_occupied']]}
    a, b = pair['condition_a'], pair['condition_b']
    if (a['turn_index'] != 301 or b['turn_index'] != 181
            or a['cycles_at_turn'] != 2 or b['cycles_at_turn'] != 1
            or a['road_sha256'] != b['road_sha256']
            or a['road_geometry_sha256'] != b['road_geometry_sha256']
            or a['pedestrian_conflict_frames'] != b['pedestrian_conflict_frames']
            or a['traffic_conflict_frames'] != b['traffic_conflict_frames']):
        raise ValueError('Controlled two-cycle comparison isolation failed')
    report = {'format': 'c110919-selected-cpu-comparison-audit', 'passed': True,
              'execution_manifest_sha256': sha(HERE / 'execution-manifest.json'),
              'conditions': pair, 'original_native_observed': False,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / 'selected-comparison-audit.json'
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(target),
                      'turn_indexes': [a['turn_index'], b['turn_index']]}))


if __name__ == '__main__':
    audit()
