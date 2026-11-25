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
    construction = read(ROOT / entry['construction'])
    config = read_config(construction)
    road = read(attempt / 'road_geometry.json')
    road_contract = {key: value for key, value in road.items() if key not in (
        'original_source_sha256', 'review_sha256', 'physical_detector_causation_verified',
        'signal_actor_id', 'cross_signal_actor_id')}
    return {'case_id': entry['case_id'], 'road_sha256': source_hashes['road_geometry.json'],
            'road_contract': road_contract, 'signal_actor_ids': (
                road['signal_actor_id'], road['cross_signal_actor_id']),
            'camera_contract': config['cameras'],
            'camera_sha256': [source_hashes[name + '.mkv'] for name in (
                'overview', 'approach', 'reference_corner', 'driver_reference')],
            'rows': rows, 'saved_sha256': sha(path)}


def read_config(construction):
    source = next((item.get('content') for item in construction['files']
                   if item['path'] == 'config.json'), None)
    if source is None:
        raise ValueError('Selected camera configuration absent')
    return json.loads(source)


def load_original(case_id, attempt, processing):
    """Load an actual saved attempt without using a fixture receipt path."""
    attempt, processing = Path(attempt), Path(processing)
    entry = next((c for c in read(ROOT / 'execution-manifest.json')['cases']
                  if c['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Comparison case is not selected')
    capture = read(attempt / 'capture' / 'manifest.json')
    if capture.get('source_kind') != 'original_native':
        raise ValueError('Original Native comparison source required')
    selection = read(attempt / 'candidate-selection.json')
    candidate_id = selection.get('candidate_id')
    selected = entry if candidate_id == 'primary' else next(
        (candidate for candidate in entry.get('candidates', [])
         if candidate['id'] == candidate_id), None)
    if selected is None:
        raise ValueError('Comparison candidate is not selected')
    construction = ROOT / selected['construction']
    if sha(construction) != selected['construction_sha256']:
        raise ValueError('Comparison selected construction changed')
    if (selection.get('case_id') != case_id or
            selection.get('construction_sha256') != selected['construction_sha256'] or
            selection.get('manifest_sha256') != sha(ROOT / 'execution-manifest.json')):
        raise ValueError('Comparison candidate selection differs')
    receipt = read(processing)
    if (receipt.get('case_id') != case_id or receipt.get('candidate_id') != candidate_id or
            receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('timestamp_joins', {}).get('frames') != 600 or
            receipt.get('final_video_checks', {}).get('passed') is not True or
            receipt.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Original comparison saved proof incomplete')
    hashes = receipt.get('original_source_hashes', {})
    original_sources = ('native_raw_readback.jsonl', 'video_frames.jsonl',
                        'map-import-survey.json', 'overview.mkv', 'approach.mkv',
                        'reference_corner.mkv', 'driver_reference.mkv')
    for source in (*original_sources, 'source-review.json', 'native_samples.jsonl',
                   'road_geometry.json'):
        path = attempt / source
        if not path.is_file() or sha(path) != hashes.get(source):
            raise ValueError('Original comparison source missing or changed: ' + source)
    review = read(attempt / 'source-review.json')
    if (review.get('review_kind') != 'original_source_review' or
            not isinstance(review.get('reviewer'), str) or
            not review['reviewer'].strip() or
            review.get('source_sha256') != {name: hashes[name] for name in original_sources}):
        raise ValueError('Original comparison source review missing or stale')
    rows = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(rows) != 600 or len(frames) != 600 or any(
            row['native_frame'] != frame['carla_frame'] or frame['video_frame'] != i or
            abs(row['time_s'] - frame['time_s']) > 1e-8
            for i, (row, frame) in enumerate(zip(rows, frames))):
        raise ValueError('Original comparison frame join differs')
    road = read(attempt / 'road_geometry.json')
    if (road.get('original_source_sha256') != review['source_sha256'] or
            road.get('review_sha256') != hashes['source-review.json']):
        raise ValueError('Original comparison road review provenance differs')
    road_contract = {key: value for key, value in road.items() if key not in (
        'original_source_sha256', 'review_sha256', 'physical_detector_causation_verified',
        'signal_actor_id', 'cross_signal_actor_id')}
    config = read_config(read(construction))
    return {'case_id': case_id, 'road_sha256': hashes['road_geometry.json'],
            'road_contract': road_contract, 'signal_actor_ids': (
                road['signal_actor_id'], road['cross_signal_actor_id']),
            'camera_contract': config['cameras'],
            'camera_sha256': [hashes[name + '.mkv'] for name in (
                'overview', 'approach', 'reference_corner', 'driver_reference')],
            'rows': rows, 'saved_sha256': sha(processing)}


def compare(first, second, kind):
    if first['road_contract'] != second['road_contract']:
        raise ValueError('Comparison changed fixed road source contract')
    if first['camera_contract'] != second['camera_contract']:
        raise ValueError('Comparison changed fixed camera source contract')
    left, right = first['rows'], second['rows']
    fixed = ('ego_face_observed', 'actor_class_observed', 'detector_request_present',
             'detector_request_serviced', 'other_device_prohibition_observed')
    for i, (a, b) in enumerate(zip(left, right)):
        if ((a.get('signal_actor_id'), a.get('cross_signal_actor_id')) != first['signal_actor_ids']
                or (b.get('signal_actor_id'), b.get('cross_signal_actor_id')) != second['signal_actor_ids']):
            raise ValueError('Comparison signal actor differs from its own road source at frame ' + str(i))
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


def audit_original(first_case, first_attempt, first_processing,
                   second_case, second_attempt, second_processing, kind, output):
    expected = {
        'cycle_wait': ('probe_1', 'probe_2'),
        'yield_clearance': ('yield_wait_for_clearance', 'yield_enter_during_occupancy'),
    }
    if kind not in expected or (first_case, second_case) != tuple(
            ROOT.name + '__' + suffix for suffix in expected[kind]):
        raise ValueError('Original comparison pair differs from the exact case plan')
    first = load_original(first_case, first_attempt, first_processing)
    second = load_original(second_case, second_attempt, second_processing)
    value = compare(first, second, kind)
    value['original_native_verified'] = True
    value['diagnostic_only'] = False
    value['physical_acceptance_claimed'] = False
    value['legal_acceptance_claimed'] = False
    output = Path(output)
    if output.exists():
        raise ValueError('Retain previous comparison audit')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + '\n')
    return value


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
        return left, {**right, 'road_contract': {'changed': True}}
    def bad_camera(left, right):
        return left, {**right, 'camera_contract': [{'changed': True}]}
    def bad_face(left, right):
        rows = [dict(row) for row in right['rows']]
        rows[0]['ego_face_observed'] = 'changed'
        return left, {**right, 'rows': rows}
    def bad_actor_binding(left, right):
        rows = [dict(row) for row in right['rows']]
        rows[0]['signal_actor_id'] = -1
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
    reject(bad_camera, sources['probe_1'], sources['probe_2'], 'cycle_wait', 'changed fixed camera')
    reject(bad_face, sources['probe_1'], sources['probe_2'], 'cycle_wait', 'changed fixed signal')
    reject(bad_actor_binding, sources['probe_1'], sources['probe_2'], 'cycle_wait', 'differs from its own road')
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
    for name in ('first-case', 'first-attempt', 'first-processing',
                 'second-case', 'second-attempt', 'second-processing', 'kind', 'output'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if args.prove:
        prove()
    else:
        required = ('first_case', 'first_attempt', 'first_processing',
                    'second_case', 'second_attempt', 'second_processing', 'kind', 'output')
        if any(getattr(args, name) is None for name in required):
            parser.error('Original comparison requires two exact cases, attempts, processing receipts, kind and output')
        result = audit_original(*(getattr(args, name) for name in required))
        print(json.dumps({'case_ids': result['case_ids'],
                          'original_native_verified': True, 'physical_acceptance_claimed': False}))
