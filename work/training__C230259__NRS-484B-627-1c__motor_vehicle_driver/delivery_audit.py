"""Independent original-route acceptance gate; diagnostic selftest only."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def check_result(result, case):
    require(result.get('case_id') == case and result.get('provenance_kind') == 'native'
            and result.get('diagnostic_fixture') is not True,
            'Missing original source: exact original Native result')
    require(result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met'
            and result.get('maneuver_completed') is True and result.get('setup_confirmed') is True,
            'Original physical movement or setup incomplete')
    require(result.get('accepted') is False and result.get('legal_verdict_claimed') is False,
            'Finalizer improperly preaccepted a legal outcome')
    measured = result.get('measured_values', {})
    require(measured.get('frames') == 900 and measured.get('duration_s') == 45.0
            and measured.get('immediately_following_approach_frames', 0) >= 20,
            'Missing source-bound original follower and route measurement')
    require(measured.get('controlled_access_designation_independently_verified') is False
            and measured.get('impediment_legally_determined') is False,
            'Finalizer asserted an unreviewed legal fact')
    channels = {row.get('name') for row in result.get('recording_evidence', [])}
    require({'participant_motion', 'route_occupancy'} <= channels,
            'Original participant or route channel missing')


def inside(folder, name):
    path = (folder / name).resolve()
    require(folder.resolve() in path.parents and path.is_file(),
            'Missing original source: ' + name)
    return path


def audit(case, attempt, review_path, output):
    from route_measure import measure
    from scenario_pipeline.worker_exchange import media
    attempt = Path(attempt).resolve()
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, case)
    names = ('route-trace.jsonl', 'route-context.json', 'road.xodr', 'video_frames.jsonl')
    sources = {name: inside(attempt, name) for name in names}
    measured = measure(*(sources[name].read_bytes() for name in names))
    require(measured['source_kind'] == 'native_saved_sample',
            'Diagnostic route source cannot be delivered')
    review = json.loads(inside(attempt, review_path).read_text())
    require(review.get('format') == 'c230259-independent-route-review-v1'
            and review.get('case_id') == case and review.get('reviewer_id')
            and review.get('source_kind') == 'original_native_review',
            'Missing independent original route review')
    require(review.get('source_sha256') == measured['source_sha256'],
            'Independent review source hashes changed')
    require(review.get('controlled_access_designation_verified') is True
            and review.get('immediately_following_impediment_verified') is True
            and isinstance(review.get('alternate_route_practically_possible'), bool)
            and review.get('actual_route_use_verified') is True,
            'Independent statutory source review incomplete')
    frames = review.get('reviewed_frames')
    require(isinstance(frames, list) and frames and all(type(i) is int and 0 <= i < 900 for i in frames),
            'No decisive original pixels reviewed')
    for row in result['recording_evidence']:
        inside(attempt, row['reference'])
    videos = {name: inside(attempt, name + '.mkv') for name in
              ('overview', 'approach', 'reference_corner', 'driver_reference')}
    decode = {}
    for name, video in videos.items():
        receipt = Path(output).with_name('decode-' + name + '.json')
        media.audit(video, 900, mapping_sha256=sha(sources['video_frames.jsonl']), receipt=receipt)
        media.verify_receipt(video, receipt, 900,
                             mapping_sha256=sha(sources['video_frames.jsonl']))
        decode[name] = {'video_sha256': sha(video), 'decode_sha256': sha(receipt)}
    payload = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': case,
               'checks': {name: True for name in CHECKS},
               'source_result_sha256': sha(result_path),
               'source_sha256': measured['source_sha256'], 'four_views': decode,
               'review_sha256': sha(inside(attempt, review_path)),
               'physical_acceptance_claimed_by_fixture': False}
    Path(output).write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'physical_checks': {'maneuver': {'status': 'met'}},
              'maneuver_completed': True, 'setup_confirmed': True,
              'accepted': False, 'legal_verdict_claimed': False,
              'measured_values': {'frames': 900, 'duration_s': 45.0,
                                  'immediately_following_approach_frames': 20,
                                  'controlled_access_designation_independently_verified': False,
                                  'impediment_legally_determined': False},
              'recording_evidence': [{'name': 'participant_motion'},
                                     {'name': 'route_occupancy'}]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Diagnostic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('recording_evidence', [])):
        changed = json.loads(json.dumps(sample))
        changed[key] = value
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Incomplete source accepted')
    return {'case_id': case, 'source_predicates_tested': True,
            'original_native_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--review', default='route-review.json')
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else
                     audit(args.case, args.attempt, args.review, args.output), indent=2))
