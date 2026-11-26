"""Independent original-source acceptance predicate for opposite-direction meeting."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
TOPICS = ('pavement_edges', 'opposite_directions', 'one_lane_each_direction',
          'physical_constraints', 'body_footprints')
SOURCES = ('capture-seal.json', 'pavement-survey.json', 'native-motion.jsonl',
           'video_frames.jsonl', *(name + '.mkv' for name in CAMERAS))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def inside(root, name):
    path = (root / name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
        raise ValueError('Missing original source: exact original Native result')
    metric = result.get('measured_values', {})
    if metric.get('source_kind') != 'original_native' or metric.get('diagnostic_fixture') is not False or metric.get('frame_count') != 600 or metric.get('legal_compliance') != 'unassessed':
        raise ValueError('Original measurement incomplete or premature legal claim')
    if not metric.get('source_review_sha256'):
        raise ValueError('Separate original source review missing')
    if set(metric.get('source_sha256', {})) != {'pavement-survey.json', 'native-motion.jsonl', 'video_frames.jsonl'}:
        raise ValueError('Original source hashes incomplete')
    if set(metric.get('camera_video_sha256', {})) != set(CAMERAS):
        raise ValueError('Original camera hashes incomplete')
    if not isinstance(metric.get('first_meeting_frame'), int) or not metric.get('ego_passed_to_right_of_other_center'):
        raise ValueError('Original opposite-direction meeting unmeasured')
    halves = metric.get('one_half_paved_portion_condition', {})
    if not all(isinstance(halves.get(key), (int, float)) for key in ('minimum_width_available_to_oncoming_m', 'minimum_width_available_to_ego_m', 'minimum_fraction_available_to_oncoming', 'minimum_fraction_available_to_ego')) or halves.get('as_nearly_as_possible') != 'unassessed':
        raise ValueError('Both drivers and unresolved paved-half judgment not measured')
    if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original physical meeting completion unproven')
    return metric


def check_review(review, case, video, mapping, metric):
    if review.get('format') != 'c230259-original-pixel-and-law-review-v1' or review.get('case_id') != case or not review.get('reviewer_id') or review.get('source_kind') != 'original_native_review':
        raise ValueError('Missing source-bound original pixel and law review')
    if review.get('video_sha256') != sha(video) or review.get('video_frames_sha256') != sha(mapping):
        raise ValueError('Original review video/frame binding differs')
    for key in ('ego_visible', 'oncoming_visible', 'both_full_bodies_visible',
                'paved_edges_visible', 'one_lane_each_direction_confirmed',
                'opposite_motion_confirmed', 'as_nearly_as_possible_reviewed'):
        if review.get('findings', {}).get(key) is not True:
            raise ValueError('Original pixel/law finding missing: ' + key)
    if review.get('decisive_frames', {}).get('meeting') != metric['first_meeting_frame']:
        raise ValueError('Original decisive meeting frame review incomplete')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt, output = Path(args.attempt).resolve(), Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain prior independent audit')
    result_path = inside(attempt, 'result.json')
    metric = check_result(read(result_path), args.case)
    for name, digest in metric['source_sha256'].items():
        if sha(inside(attempt, name)) != digest:
            raise ValueError('Original measurement source hash differs: ' + name)
    for name, digest in metric['camera_video_sha256'].items():
        if sha(inside(attempt, name + '.mkv')) != digest:
            raise ValueError('Original camera source hash differs: ' + name)
    seal = read(inside(attempt, 'capture-seal.json'))
    if seal.get('format') != 'worker-sealed-capture' or seal.get('diagnostic_fixture') is True:
        raise ValueError('Missing sealed original Native acquisition')
    source_review_path = inside(attempt, 'source-review.json')
    source_review = read(source_review_path)
    if sha(source_review_path) != metric['source_review_sha256'] or source_review.get('format') != 'worker-original-meeting-source-review' or source_review.get('case_id') != args.case:
        raise ValueError('Original source review binding differs')
    if set(source_review.get('source_sha256', {})) != set(SOURCES) or any(sha(inside(attempt, name)) != source_review['source_sha256'][name] for name in SOURCES):
        raise ValueError('Original source review inventory differs')
    if any(source_review.get('confirmed_topics', {}).get(topic, {}).get('confirmed') is not True for topic in TOPICS):
        raise ValueError('Original source review topics incomplete')
    mapping = inside(attempt, 'video_frames.jsonl')
    rows = [json.loads(line) for line in mapping.read_text().splitlines()]
    if len(rows) != 600 or any(row.get('video_frame') != i or row.get('camera_native_frames') != {name: row.get('native_frame') for name in CAMERAS} for i, row in enumerate(rows)):
        raise ValueError('Original four-camera frame map incomplete')
    video, trace = inside(attempt, args.video), inside(attempt, args.trace)
    scenes = read(trace).get('scenes', [])
    if len(scenes) != 600 or any(scene.get('t') != round(row['time_s'] * 1000) for scene, row in zip(scenes, rows)):
        raise ValueError('Original Core/frame time join differs')
    review = inside(attempt, args.review)
    check_review(read(review), args.case, video, mapping, metric)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(mapping), receipt=decode)
    media.verify_receipt(video, decode, 600, mapping_sha256=sha(mapping))
    value = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job, 'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'video_sha256': sha(video),
             'trace_sha256': sha(trace), 'human_review_sha256': sha(review),
             'checks': {key: True for key in CHECKS},
             'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + '\n')
    return value


def selftest(case, negative):
    metric = {'source_kind': 'original_native', 'diagnostic_fixture': False,
              'frame_count': 600, 'legal_compliance': 'unassessed',
              'source_review_sha256': '0' * 64,
              'source_sha256': {name: '0' * 64 for name in
                  ('pavement-survey.json', 'native-motion.jsonl', 'video_frames.jsonl')},
              'camera_video_sha256': {name: '0' * 64 for name in CAMERAS},
              'first_meeting_frame': 230, 'ego_passed_to_right_of_other_center': True,
              'one_half_paved_portion_condition': {
                  'minimum_width_available_to_oncoming_m': 4.0,
                  'minimum_width_available_to_ego_m': 4.0,
                  'minimum_fraction_available_to_oncoming': 0.5,
                  'minimum_fraction_available_to_ego': 0.5,
                  'as_nearly_as_possible': 'unassessed'}}
    sample = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'measured_values': metric,
              'physical_checks': {'maneuver': {'status': 'met'}},
              'maneuver_completed': True}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
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
            raise AssertionError('Missing original source accepted: ' + name)
    findings = {key: True for key in ('ego_visible', 'oncoming_visible',
                'both_full_bodies_visible', 'paved_edges_visible',
                'one_lane_each_direction_confirmed', 'opposite_motion_confirmed',
                'as_nearly_as_possible_reviewed')}
    source = Path(__file__)
    review = {'format': 'c230259-original-pixel-and-law-review-v1',
              'case_id': case, 'reviewer_id': 'cpu-predicate-test',
              'source_kind': 'original_native_review',
              'video_sha256': sha(source), 'video_frames_sha256': sha(source),
              'findings': findings, 'decisive_frames': {'meeting': 230}}
    check_review(review, case, source, source, metric)
    review['findings'].pop('as_nearly_as_possible_reviewed')
    try:
        check_review(review, case, source, source, metric)
    except ValueError:
        pass
    else:
        raise AssertionError('Missing statutory review accepted')
    print(json.dumps({'case_id': case, 'cpu_predicates_passed': True,
                      'original_acquisition_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    parser.add_argument('--video')
    parser.add_argument('--trace')
    parser.add_argument('--review')
    parser.add_argument('--job')
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    selftest(args.case, args.negative) if args.self_test else audit(args)
