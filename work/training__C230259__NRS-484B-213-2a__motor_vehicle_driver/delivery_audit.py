"""Independent source gate for original Native crest and curve deliveries."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode', 'actual_pixels',
          'physical_completion', 'independent_sight_and_hazard_review')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def inside(folder, name):
    path = (Path(folder) / name).resolve()
    require(Path(folder).resolve() in path.parents and path.is_file(),
            'Missing original source: ' + name)
    return path


def check_result(result, case):
    require(result.get('case_id') == case and result.get('provenance_kind') == 'original_native_attempt'
            and result.get('diagnostic_fixture') is not True,
            'Missing original source: exact original Native result')
    require(result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met'
            and result.get('maneuver_completed') is True and result.get('setup_confirmed') is True,
            'Original physical feature or maneuver incomplete')
    require(result.get('accepted') is False and result.get('legal_verdict_claimed') is False,
            'Unreviewed legal acceptance asserted')
    measured = result.get('measured_values', {})
    require(measured.get('frames') == 600 and measured.get('rate_hz') == 20
            and measured.get('feature_kind') in ('crest', 'curve')
            and measured.get('feature_frame_count', 0) > 0,
            'Missing source-bound original feature measurement')
    require(measured.get('hazard_distance_legal_judgment') is None,
            'Unreviewed hazard distance asserted')
    names = {row.get('name') for row in result.get('recording_evidence', [])}
    require({'st.grade', 'st.curvature', 'st.sight_distance', 'rel.occupies',
             'st.one_way_roadway', 'rel.oncoming'} <= names,
            'Original feature channels missing')


def audit(case, attempt, review_name, output):
    from scenario_pipeline.worker_exchange import media
    from measure_feature import measure, read_rows
    attempt = Path(attempt).resolve()
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, case)
    source_names = ('native-feature-source.jsonl', 'road-context.json',
                    'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                    'road.xodr')
    sources = {name: inside(attempt, name) for name in source_names}
    road = json.loads(sources['road-context.json'].read_text())
    require(road.get('source_kind') == 'original_native_map_readback_pending_review' and
            road.get('roadside_occluder_request', {}).get('height_m') == 4.0,
            'Original wall and road readback missing')
    metric = measure(sources['native-feature-source.jsonl'], sources['road-context.json'])
    require(metric == result['measured_values'], 'Original feature measurements changed')
    participants = read_rows(sources['native-feature-source.jsonl'])
    require(len(participants) == 600 and all(row.get('ego_id') is not None
            and row.get('other_vehicle_id') is not None
            and row.get('other_vehicle_route_direction') in ('same', 'opposing')
            for row in participants), 'Original all-participant source incomplete')
    joins = read_rows(sources['video_frames.jsonl'])
    require(len(joins) == 600 and [r.get('video_frame') for r in joins] == list(range(600)),
            'Original four-view frame join missing')
    review = json.loads(inside(attempt, review_name).read_text())
    require(review.get('format') == 'c230259-independent-feature-review-v1'
            and review.get('case_id') == case and review.get('reviewer_id')
            and review.get('source_kind') == 'original_native_review',
            'Missing independent original sight and hazard review')
    require(review.get('source_sha256') == {name: sha(path) for name, path in sources.items()}
            and review.get('sightline_obstruction_verified') is True
            and review.get('hazard_creating_distance_reviewed') is True
            and isinstance(review.get('public_highway_designation_verified'), bool)
            and review.get('road_directionality_verified') is True,
            'Independent source review incomplete or changed')
    frames = review.get('reviewed_frames')
    require(isinstance(frames, list) and frames and all(type(i) is int and 0 <= i < 600 for i in frames),
            'No decisive original pixels reviewed')
    decode = {}
    for name in CAMERAS:
        video = inside(attempt, name + '.mkv')
        receipt = Path(output).with_name('decode-' + name + '.json')
        media.audit(video, 600, mapping_sha256=sha(sources['video_frames.jsonl']), receipt=receipt)
        media.verify_receipt(video, receipt, 600,
                             mapping_sha256=sha(sources['video_frames.jsonl']))
        decode[name] = {'video_sha256': sha(video), 'decode_sha256': sha(receipt)}
    payload = {'format': 'worker-delivery-audit', 'case_id': case, 'passed': True,
               'checks': {name: True for name in CHECKS},
               'source_result_sha256': sha(result_path), 'four_views': decode,
               'review_sha256': sha(inside(attempt, review_name)),
               'physical_acceptance_claimed_by_fixture': False}
    Path(output).write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'original_native_attempt', 'diagnostic_fixture': False,
              'physical_checks': {'maneuver': {'status': 'met'}},
              'maneuver_completed': True, 'setup_confirmed': True,
              'accepted': False, 'legal_verdict_claimed': False,
              'measured_values': {'frames': 600, 'rate_hz': 20, 'feature_kind': 'curve',
                                  'approach_frame_count': 40, 'feature_frame_count': 100,
                                  'hazard_distance_legal_judgment': None},
              'recording_evidence': [{'name': n} for n in
                 ('st.grade', 'st.curvature', 'st.sight_distance', 'rel.occupies',
                  'st.one_way_roadway', 'rel.oncoming')]}
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
            raise AssertionError('Incomplete original source accepted')
    return {'case_id': case, 'source_predicates_tested': True,
            'original_native_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--review', default='feature-review.json')
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else
                     audit(args.case, args.attempt, args.review, args.output), indent=2))
