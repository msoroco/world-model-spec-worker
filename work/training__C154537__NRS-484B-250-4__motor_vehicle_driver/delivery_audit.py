"""Independent source and human-review audit for C154537 selected Native cases."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
SOURCE_FILES = ('capture-seal.json', 'scene-survey.json', 'native-motion.jsonl',
                'video_frames.jsonl', 'overview.mkv', 'approach.mkv',
                'reference_corner.mkv', 'driver_reference.mkv')
REVIEW_TOPICS = ('stop_line', 'near_side_crosswalk', 'sidewalk_crosswalk',
                 'uncovered_official_signal', 'through_highway', 'driver_view')


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
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is True):
        raise ValueError('Missing original source: exact original Native result')
    metric = result.get('measured_values', {})
    if (metric.get('source_kind') != 'original_native' or
            metric.get('diagnostic_fixture') is not False or
            metric.get('frame_count') != 600 or metric.get('legal_verdict_claimed') is not False):
        raise ValueError('Original measurement incomplete or premature legal claim')
    for name in ('scene-survey.json', 'native-motion.jsonl', 'video_frames.jsonl'):
        if not metric.get('source_sha256', {}).get(name):
            raise ValueError('Missing source-bound original measurement: ' + name)
    if not isinstance(metric.get('entry_frame'), int):
        raise ValueError('Physical intersection entry unmeasured')
    stopped = not case.endswith('controlled_2')
    if metric.get('complete_cessation_sample_before_entry') is not stopped:
        raise ValueError('Physical stop contrast differs from selected case')
    binding = metric.get('source_review')
    if not isinstance(binding, dict) or len(binding.get('confirmed_topics', [])) != 6:
        raise ValueError('Separate original source review missing from measurement')
    physical = result.get('physical_checks', {}).get('maneuver', {})
    if physical.get('status') != 'met' or result.get('maneuver_completed') is not True:
        raise ValueError('Original full-body intersection clearance unproven')
    return metric


def check_review(review, case, video, mapping, metric):
    if (review.get('format') != 'c154537-original-pixel-and-law-review-v1'
            or review.get('source_kind') != 'original_native_review'
            or review.get('case_id') != case or not review.get('reviewer_id')
            or review.get('video_sha256') != sha(video)
            or review.get('video_frames_sha256') != sha(mapping)):
        raise ValueError('Missing source-bound original pixel and law review')
    findings = review.get('findings', {})
    required = ['ego_visible', 'other_visible', 'both_heads_uncovered',
                'both_heads_dark', 'official_device_confirmed',
                'through_highway_confirmed',
                'approaching_traffic_visible', 'cautious_proceeding_reviewed',
                'prior_stop_and_intersection_yield_reviewed']
    if case.endswith('controlled_3'):
        required += ['marked_line_confirmed', 'no_near_side_crosswalk']
    elif case.endswith('controlled_4'):
        required += ['no_marked_line', 'near_side_crosswalk_confirmed']
    else:
        required += ['no_marked_line', 'no_near_side_crosswalk',
                     'nearest_view_point_confirmed']
    if case.endswith('controlled_5'):
        required.append('other_prior_stop_confirmed')
    elif case.endswith('controlled_6'):
        required.append('other_inside_at_ego_entry_confirmed')
    elif case.endswith('controlled_7'):
        required.append('other_clear_at_ego_entry_confirmed')
    for key in required:
        if findings.get(key) is not True:
            raise ValueError('Original pixel/law finding missing: ' + key)
    frames = review.get('decisive_frames', {})
    if (not isinstance(frames.get('ego_entry'), int)
            or frames['ego_entry'] != metric['entry_frame']
            or not isinstance(frames.get('governing_reference'), int)):
        raise ValueError('Original decisive frame review incomplete')


def check_source_review(attempt, path, binding):
    review = read(path)
    if review.get('format') != 'c154537-source-context-review-v1' or \
            not review.get('reviewer') or not review.get('review_method'):
        raise ValueError('Separate original source review incomplete')
    hashes = review.get('original_sha256')
    if not isinstance(hashes, dict) or set(hashes) != set(SOURCE_FILES):
        raise ValueError('Separate original source inventory incomplete')
    for name in SOURCE_FILES:
        if sha(inside(attempt, name)) != hashes[name]:
            raise ValueError('Separate original source hash differs: ' + name)
    topics = review.get('topics')
    if not isinstance(topics, dict) or set(topics) != set(REVIEW_TOPICS):
        raise ValueError('Separate original review topics incomplete')
    for name, item in topics.items():
        if item.get('status') != 'confirmed' or not item.get('observation') or \
                not item.get('reason') or not item.get('source_refs') or \
                not set(item['source_refs']) <= set(SOURCE_FILES):
            raise ValueError('Separate original review topic incomplete: ' + name)
    expected = {'format': 'c154537-reviewed-source-context-v1',
                'review_sha256': hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest(),
                'confirmed_topics': sorted(REVIEW_TOPICS), 'unresolved_topics': [],
                'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    if binding != expected:
        raise ValueError('Original source review binding differs')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt, output = Path(args.attempt).resolve(), Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain prior independent audit')
    result_path = inside(attempt, 'result.json')
    result = read(result_path)
    metric = check_result(result, args.case)
    for name, digest in metric['source_sha256'].items():
        if sha(inside(attempt, name)) != digest:
            raise ValueError('Original measurement source hash differs: ' + name)
    seal = read(inside(attempt, 'capture-seal.json'))
    if seal.get('format') != 'worker-sealed-capture' or seal.get('diagnostic_fixture') is True:
        raise ValueError('Missing sealed original Native acquisition')
    mapping = inside(attempt, 'video_frames.jsonl')
    rows = [json.loads(line) for line in mapping.read_text().splitlines()]
    if len(rows) != 600 or any(row.get('video_frame') != i for i, row in enumerate(rows)):
        raise ValueError('Original frame map incomplete')
    video = inside(attempt, args.video)
    trace = inside(attempt, args.trace)
    scenes = read(trace).get('scenes', [])
    if len(scenes) != 600 or any(scene.get('t') != round(row['time_s'] * 1000)
                                  for scene, row in zip(scenes, rows)):
        raise ValueError('Original Core/frame time join differs')
    review = inside(attempt, args.review)
    source_review = inside(attempt, 'source-review.json')
    check_source_review(attempt, source_review, metric['source_review'])
    check_review(read(review), args.case, video, mapping, metric)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(mapping), receipt=decode)
    media.verify_receipt(video, decode, 600, mapping_sha256=sha(mapping))
    value = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job,
             'recording_id': args.recording_id, 'source_result_sha256': sha(result_path),
             'video_sha256': sha(video), 'trace_sha256': sha(trace),
             'human_review_sha256': sha(review),
             'checks': {key: True for key in CHECKS},
             'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + '\n')
    return value


def selftest(case, negative):
    metric = {'source_kind': 'original_native', 'diagnostic_fixture': False,
              'frame_count': 600, 'legal_verdict_claimed': False,
              'source_sha256': {name: '0' * 64 for name in
                  ('scene-survey.json', 'native-motion.jsonl', 'video_frames.jsonl')},
              'entry_frame': 225,
              'complete_cessation_sample_before_entry': not case.endswith('controlled_2'),
              'source_review': {'confirmed_topics': ['stop_line', 'near_side_crosswalk',
                'sidewalk_crosswalk', 'uncovered_official_signal',
                'through_highway', 'driver_view']}}
    sample = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'measured_values': metric,
              'physical_checks': {'maneuver': {'status': 'met'}},
              'maneuver_completed': True}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for missing in metric['source_sha256']:
        changed = json.loads(json.dumps(sample))
        changed['measured_values']['source_sha256'].pop(missing)
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing source hash accepted: ' + missing)
    findings = {key: True for key in (
        'ego_visible', 'other_visible', 'both_heads_uncovered', 'both_heads_dark',
        'official_device_confirmed', 'through_highway_confirmed',
        'approaching_traffic_visible', 'cautious_proceeding_reviewed',
        'prior_stop_and_intersection_yield_reviewed', 'no_marked_line',
        'no_near_side_crosswalk', 'nearest_view_point_confirmed',
        'marked_line_confirmed', 'near_side_crosswalk_confirmed',
        'other_prior_stop_confirmed', 'other_inside_at_ego_entry_confirmed',
        'other_clear_at_ego_entry_confirmed')}
    source = Path(__file__)
    review = {'format': 'c154537-original-pixel-and-law-review-v1',
              'source_kind': 'original_native_review', 'case_id': case,
              'reviewer_id': 'cpu-predicate-test', 'video_sha256': sha(source),
              'video_frames_sha256': sha(source), 'findings': findings,
              'decisive_frames': {'ego_entry': 225, 'governing_reference': 131}}
    check_review(review, case, source, source, metric)
    case_key = ('marked_line_confirmed' if case.endswith('controlled_3') else
                'near_side_crosswalk_confirmed' if case.endswith('controlled_4') else
                'other_prior_stop_confirmed' if case.endswith('controlled_5') else
                'other_inside_at_ego_entry_confirmed' if case.endswith('controlled_6') else
                'other_clear_at_ego_entry_confirmed' if case.endswith('controlled_7') else
                'nearest_view_point_confirmed')
    review['findings'].pop(case_key)
    try:
        check_review(review, case, source, source, metric)
    except ValueError as error:
        if case_key not in str(error):
            raise
    else:
        raise AssertionError('Missing case-specific review accepted')
    return {'case_id': case, 'source_predicates_tested': True,
            'case_review_predicates_tested': True,
            'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    parser.add_argument('--trace', default='converted/trace.json')
    parser.add_argument('--video', default='primary.mkv')
    parser.add_argument('--review', default='human-review.json')
    parser.add_argument('--job')
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args)))
