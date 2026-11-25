"""Check source-bound straight-cycle and conflict-yield comparisons."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ('probe_1', 'probe_2', 'yield_wait_for_clearance', 'yield_enter_during_occupancy')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(suffix):
    path = ROOT / 'selected-native' / suffix / 'saved-proof.json'
    saved = read(path)
    receipt = saved['processing_receipt']
    attempt = Path(receipt['version']).parents[1] / 'attempt'
    source_hashes = receipt['original_source_hashes']
    for source in ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json',
                   'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'):
        target = attempt / source
        if not target.is_file() or sha(target) != source_hashes.get(source):
            raise ValueError('Comparison original source missing or changed: ' + source)
    rows = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(rows) != 600 or len(frames) != 600 or any(
            row['native_frame'] != frame['carla_frame'] or frame['video_frame'] != i
            or abs(row['time_s'] - frame['time_s']) > 1e-8
            for i, (row, frame) in enumerate(zip(rows, frames))):
        raise ValueError('Comparison frame join differs')
    if not receipt.get('passed') or not receipt.get('recorded_only') or not receipt.get('originals_preserved'):
        raise ValueError('Comparison saved proof incomplete')
    entry = next(c for c in read(ROOT / 'execution-manifest.json')['cases']
                 if c['case_id'].endswith('__' + suffix))
    if entry['case_id'] != saved['case_id'] or sha(ROOT / entry['construction']) != entry['construction_sha256']:
        raise ValueError('Comparison selected construction changed')
    return {'case_id': entry['case_id'], 'road_sha256': source_hashes['road_geometry.json'],
            'camera_sha256': [source_hashes[name + '.mkv'] for name in (
                'overview', 'approach', 'reference_corner', 'driver_reference')],
            'rows': rows, 'saved_sha256': sha(path)}


def compare(first, second, kind):
    if first['road_sha256'] != second['road_sha256']:
        raise ValueError('Comparison changed fixed road source')
    if first['camera_sha256'] != second['camera_sha256']:
        raise ValueError('Comparison changed fixed camera source contract')
    left, right = first['rows'], second['rows']
    fixed = ('signal_actor_id', 'cross_signal_actor_id', 'ego_face_observed',
             'actor_class_observed', 'detector_request_present',
             'detector_request_serviced', 'other_device_prohibition_observed')
    for i, (a, b) in enumerate(zip(left, right)):
        if any(a.get(field) != b.get(field) for field in fixed):
            raise ValueError('Comparison changed fixed signal or actor source at frame ' + str(i))
    if kind == 'cycle_wait':
        if any(a['pedestrians_in_crosswalk'] != b['pedestrians_in_crosswalk']
               or a['lawful_traffic_conflict'] != b['lawful_traffic_conflict']
               for a, b in zip(left, right)):
            raise ValueError('Cycle contrast changed participant schedule')
    else:
        if any(a['controller_cycle_count'] != b['controller_cycle_count']
               for a, b in zip(left, right)):
            raise ValueError('Yield contrast changed cycle history')
        if any(a['pedestrians_in_crosswalk'] != b['pedestrians_in_crosswalk']
               or a['lawful_traffic_conflict'] != b['lawful_traffic_conflict']
               for a, b in zip(left, right)):
            raise ValueError('Yield contrast changed participant schedule')
    def entry(rows):
        return next((i for i, row in enumerate(rows) if row['entered_intersection']), None)
    a, b = entry(left), entry(right)
    if a is None or b is None:
        raise ValueError('Comparison has no measured intersection entry')
    if kind == 'cycle_wait':
        if (left[a]['controller_cycle_count'], right[b]['controller_cycle_count']) != (2, 1):
            raise ValueError('Cycle comparison lacks two-versus-one source contrast')
    elif kind == 'yield_clearance':
        def conflict(row):
            return row['pedestrians_in_crosswalk'] or row['lawful_traffic_conflict']
        if (left[a]['controller_cycle_count'], right[b]['controller_cycle_count']) != (2, 2):
            raise ValueError('Yield comparison changed entry cycle count')
        if conflict(left[a]) or not conflict(right[b]):
            raise ValueError('Yield comparison lacks clear-versus-occupied entry')
    else:
        raise ValueError('Unknown comparison kind')
    return {'case_ids': [first['case_id'], second['case_id']], 'entry_frames': [a, b],
            'cycles_at_entry': [left[a]['controller_cycle_count'], right[b]['controller_cycle_count']],
            'kind': kind, 'fixed_road_sha256': first['road_sha256'],
            'saved_proof_sha256': [first['saved_sha256'], second['saved_sha256']],
            'diagnostic_only': True, 'original_native_verified': False}


def prove():
    sources = {suffix: load(suffix) for suffix in SUFFIXES}
    pairs = [compare(sources['probe_1'], sources['probe_2'], 'cycle_wait'),
             compare(sources['yield_wait_for_clearance'], sources['yield_enter_during_occupancy'], 'yield_clearance')]
    negatives = 0
    def reject(change, left, right, kind, expected):
        nonlocal negatives
        try:
            changed_left, changed_right = change(left, right)
            compare(changed_left, changed_right, kind)
        except ValueError as error:
            if expected not in str(error):
                raise
            negatives += 1
        else:
            raise ValueError('Comparison mutation was accepted')
    def bad_road(left, right):
        return left, {**right, 'road_sha256': 'changed'}
    def bad_face(left, right):
        rows = [dict(row) for row in right['rows']]
        rows[0]['ego_face_observed'] = 'changed'
        return left, {**right, 'rows': rows}
    def bad_cycle(left, right):
        rows = [dict(row) for row in right['rows']]
        for row in rows:
            if row['entered_intersection']:
                row['controller_cycle_count'] = 2
        return left, {**right, 'rows': rows}
    def bad_yield(left, right):
        rows = [dict(row) for row in right['rows']]
        for row in rows:
            if row['entered_intersection']:
                row['pedestrians_in_crosswalk'] = False
                row['lawful_traffic_conflict'] = False
        return left, {**right, 'rows': rows}
    reject(bad_road, sources['probe_1'], sources['probe_2'], 'cycle_wait', 'changed fixed road')
    reject(bad_face, sources['probe_1'], sources['probe_2'], 'cycle_wait', 'changed fixed signal')
    reject(bad_cycle, sources['probe_1'], sources['probe_2'], 'cycle_wait', 'lacks two-versus-one')
    reject(bad_yield, sources['yield_wait_for_clearance'], sources['yield_enter_during_occupancy'],
           'yield_clearance', 'changed participant schedule')
    value = {'format': 'c111071-selected-comparison-cpu-v1', 'passed': True,
             'manifest_sha256': sha(ROOT / 'execution-manifest.json'),
             'comparisons': pairs, 'negative_mutations_rejected': negatives,
             'original_native_observed': False, 'legal_acceptance_claimed': False}
    path = ROOT / 'selected-comparison-cpu-proof.json'
    path.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'comparisons': len(pairs), 'negatives': negatives, 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prove', action='store_true')
    args = parser.parse_args()
    if args.prove:
        prove()
