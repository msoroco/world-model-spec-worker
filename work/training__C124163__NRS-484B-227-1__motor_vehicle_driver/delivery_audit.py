"""Independent original-source median audit; synthetic fixtures cannot satisfy it."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
SOURCES = ('capture-seal.json', 'road.xodr', 'median-context.json',
           'native-median.jsonl', 'video_frames.jsonl',
           *(name+'.mkv' for name in CAMERAS))
TOPICS = ('two_directional_roadways', 'median_and_opening_geometry',
          'full_vehicle_footprint', 'turn_and_crossing_history',
          'four_camera_visibility')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def inside(root, name):
    path = (root/name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: '+name)
    return path


def check_result(result, case):
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
        raise ValueError('Exact original Native result missing')
    metric = result.get('measured_values', {})
    if metric.get('format') != 'worker-source-median-turn-measurement' or metric.get('diagnostic_fixture') is not False:
        raise ValueError('Original median measurement missing')
    if metric.get('frame_count') != 600 or metric.get('legal_compliance') != 'unassessed':
        raise ValueError('Original frame count missing or premature legal claim')
    if not metric.get('source_review_sha256') or set(metric.get('source_sha256', {})) != set(SOURCES[2:5]):
        raise ValueError('Original median source hashes incomplete')
    counts = metric.get('occupancy_frames', {})
    if not all(type(counts.get(name)) is int for name in
               ('median', 'opening', 'barrier', 'right_hand_roadway',
                'opposite_roadway')) or counts['median'] < 1:
        raise ValueError('Original full-body median crossing unproven')
    target = case.rsplit('__', 1)[-1]
    if target == 'through_opening' and (counts['opening'] < 1 or counts['barrier'] != 0):
        raise ValueError('Original opening-only crossing unproven')
    if target == 'across_divider' and counts['barrier'] < 1:
        raise ValueError('Original continuous-section crossing unproven')
    if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original physical left-turn completion unproven')
    return metric


def check_review(review, case, video, mapping, metric):
    if review.get('format') != 'c124163-original-pixel-and-law-review-v1' or review.get('case_id') != case or not review.get('reviewer_id') or review.get('source_kind') != 'original_native_review':
        raise ValueError('Original median pixel/source review missing')
    if review.get('video_sha256') != sha(video) or review.get('video_frames_sha256') != sha(mapping):
        raise ValueError('Original review video/frame binding differs')
    findings = review.get('findings', {})
    for name in ('ego_visible', 'both_roadways_visible',
                 'median_and_opening_visible', 'left_turn_visible',
                 'physical_crossing_confirmed'):
        if findings.get(name) is not True:
            raise ValueError('Original median pixel finding missing: '+name)
    if review.get('decisive_frames', {}).get('first_crossing') != metric['first_crossing_frame']:
        raise ValueError('Original decisive crossing frame differs')
    if review.get('legal_compliance') not in (None, 'unassessed'):
        raise ValueError('Pixel audit cannot declare statutory outcome')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt, output = Path(args.attempt).resolve(), Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain prior independent audit')
    result_path = inside(attempt, 'result.json')
    metric = check_result(read(result_path), args.case)
    for name, digest in metric['source_sha256'].items():
        if sha(inside(attempt, name)) != digest:
            raise ValueError('Original metric source hash differs: '+name)
    seal = read(inside(attempt, 'capture-seal.json'))
    if seal.get('format') != 'worker-sealed-capture' or seal.get('diagnostic_fixture') is True:
        raise ValueError('Sealed original Native acquisition missing')
    review_path = inside(attempt, 'source-review.json')
    review = read(review_path)
    if sha(review_path) != metric['source_review_sha256'] or review.get('case_id') != args.case or review.get('format') != 'worker-original-median-source-review':
        raise ValueError('Original median source review binding differs')
    bound = review.get('source_sha256', {})
    if not set(SOURCES) <= set(bound) or any(sha(inside(attempt, name)) != digest
                                         for name, digest in bound.items()):
        raise ValueError('Original median source inventory differs')
    if any(review.get('confirmed_topics', {}).get(name, {}).get('confirmed') is not True
           for name in TOPICS):
        raise ValueError('Original median geometry review incomplete')
    mapping = inside(attempt, 'video_frames.jsonl')
    rows = [json.loads(line) for line in mapping.read_text().splitlines()]
    if len(rows) != 600 or any(row.get('video_frame') != i or row.get('camera_native_frames') != {name: row.get('native_frame') for name in CAMERAS} for i, row in enumerate(rows)):
        raise ValueError('Original four-camera frame map incomplete')
    video, trace = inside(attempt, args.video), inside(attempt, args.trace)
    scenes = read(trace).get('scenes', [])
    if len(scenes) != 600 or any(scene.get('t') != round(row['time_s']*1000)
                                 for scene, row in zip(scenes, rows)):
        raise ValueError('Original Core/frame join differs')
    review_file = inside(attempt, args.review)
    check_review(read(review_file), args.case, video, mapping, metric)
    decode = output.with_name('source-decode-'+args.case.rsplit('__', 1)[-1]+'.json')
    media.audit(video, 600, mapping_sha256=sha(mapping), receipt=decode)
    media.verify_receipt(video, decode, 600, mapping_sha256=sha(mapping))
    value = {'format': 'worker-delivery-audit', 'passed': True,
        'case_id': args.case, 'job_id': args.job,
        'recording_id': args.recording_id,
        'source_result_sha256': sha(result_path), 'video_sha256': sha(video),
        'trace_sha256': sha(trace), 'human_review_sha256': sha(review_file),
        'checks': {name: True for name in CHECKS},
        'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2)+'\n')
    return value


def selftest(case, negative):
    target = case.rsplit('__', 1)[-1]
    counts = {'median': 85, 'opening': 85 if target == 'through_opening' else 0,
              'barrier': 0 if target == 'through_opening' else 85,
              'right_hand_roadway': 123, 'opposite_roadway': 482}
    metric = {'format': 'worker-source-median-turn-measurement',
        'diagnostic_fixture': False, 'frame_count': 600,
        'legal_compliance': 'unassessed',
        'source_review_sha256': '0'*64,
        'source_sha256': {name: '0'*64 for name in SOURCES[2:5]},
        'occupancy_frames': counts, 'first_crossing_frame': 78}
    sample = {'case_id': case, 'provenance_kind': 'native',
        'diagnostic_fixture': False, 'measured_values': metric,
        'maneuver_completed': True,
        'physical_checks': {'maneuver': {'status': 'met'}}}
    if negative:
        sample['provenance_kind'] = 'synthetic_local_diagnostic'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for name in metric['source_sha256']:
        changed = json.loads(json.dumps(sample))
        changed['measured_values']['source_sha256'].pop(name)
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing original source accepted: '+name)
    review = {'format': 'c124163-original-pixel-and-law-review-v1',
        'case_id': case, 'reviewer_id': 'cpu-predicate-test',
        'source_kind': 'original_native_review',
        'video_sha256': sha(Path(__file__)),
        'video_frames_sha256': sha(Path(__file__)),
        'findings': {name: True for name in ('ego_visible',
            'both_roadways_visible', 'median_and_opening_visible',
            'left_turn_visible', 'physical_crossing_confirmed')},
        'decisive_frames': {'first_crossing': 78},
        'legal_compliance': 'unassessed'}
    check_review(review, case, Path(__file__), Path(__file__), metric)
    print(json.dumps({'case_id': case, 'cpu_predicates_passed': True,
                      'original_acquisition_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    for name in ('attempt', 'output', 'video', 'trace', 'review', 'job',
                 'recording-id'):
        parser.add_argument('--'+name)
    args = parser.parse_args()
    selftest(args.case, args.negative) if args.self_test else audit(args)
