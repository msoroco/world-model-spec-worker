"""Independent original-source audit for NRS 484B.500 delivery attempts."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('original-device.json', 'original-designation.json', 'original-map.json',
           'original-route.json', 'original-review.json', 'person-activity.json',
           'traffic-direction.json', 'native-stop-trace.jsonl', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original Native exact-case result')
    if result.get('setup_confirmed') is not True or result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original physical destination rest incomplete')
    measured = result.get('measured_values', {})
    place = measured.get('designated_place', {})
    physical = measured.get('physical', {})
    if (not place.get('source_hashes') or physical.get('status') != 'met'
            or physical.get('frames') != 600 or physical.get('legal_verdict_claimed') is not False):
        raise ValueError('Missing original source-bound physical measurement')
    if {'designated_place', 'person_activity_context'} != {x.get('name') for x in result.get('recording_evidence', [])}:
        raise ValueError('Original designated-place or person context channel missing')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Finalizer preaccepted or legally characterized outcome')
    return place, physical


def check_review(review, case, attempt):
    if (review.get('format') != 'c229954-original-delivery-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Independent original designation review missing')
    for source in SOURCES:
        if review.get('source_hashes', {}).get(source) != sha(required(attempt, source)):
            raise ValueError('Original source review hash changed: ' + source)
    for name in ('device_authority_content_and_erection_reviewed',
                 'independent_designated_polygon_reviewed',
                 'person_activity_and_direction_reviewed',
                 'actual_four_view_pixels_reviewed',
                 'vehicle_body_and_rest_reviewed'):
        if review.get(name) is not True:
            raise ValueError('Original review incomplete: ' + name)
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(i) is not int or i < 0 or i >= 600 for i in frames):
        raise ValueError('Decisive original pixel frame review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Review cannot claim legal verdict')


def check_joins(attempt, result):
    read = lambda name: [json.loads(line) for line in required(attempt, name).read_text().splitlines()]
    mapping, native, trace, evidence = (read(n) for n in
        ('video_frames.jsonl', 'native-stop-trace.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'))
    if any(len(rows) != 600 for rows in (mapping, native, trace, evidence)):
        raise ValueError('Original frame count differs')
    for i, (frame, body, core, scene) in enumerate(zip(mapping, native, trace, evidence)):
        if (frame.get('video_frame') != i or body.get('video_frame') != i
                or frame.get('native_frame') != body.get('native_frame')
                or core.get('frame') != body.get('native_frame')
                or scene.get('original_frame') != body.get('native_frame')):
            raise ValueError('Original source time join differs')
    if not all(required(attempt, x['reference']) for x in result['recording_evidence']):
        raise ValueError('Original channel source missing')
    activity = json.loads(required(attempt, 'person-activity.json').read_text())
    directions = json.loads(required(attempt, 'traffic-direction.json').read_text())
    if not activity.get('person_caused_stop') or not all(activity.get(k) for k in
            ('purpose_source', 'attendance_source', 'passenger_activity_source',
             'merchandise_activity_source')) or not all(directions.get(k) for k in
            ('traffic_conflicts_source', 'officer_direction_source', 'device_direction_source')):
        raise ValueError('Original person or direction source incomplete')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit must run in local operations')
    result_path = required(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    place, physical = check_result(result, args.case)
    check_review(json.loads(required(attempt, args.review).read_text()), args.case, attempt)
    check_joins(attempt, result)
    source_hashes = place['source_hashes']
    for key, name in (('device', 'original-device.json'), ('designation', 'original-designation.json'),
                      ('map', 'original-map.json'), ('person_activity', 'person-activity.json'),
                      ('traffic_direction', 'traffic-direction.json'),
                      ('native_trace', 'native-stop-trace.jsonl'), ('video_frame_map', 'video_frames.jsonl')):
        if source_hashes.get(key) != sha(required(attempt, name)):
            raise ValueError('Measured original source hash changed: ' + name)
    receipts = {}
    for video in VIDEOS:
        path = required(attempt, video)
        receipt = output.with_name(output.stem + '-' + video + '.json')
        media.audit(path, 600, mapping_sha256=sha(required(attempt, 'video_frames.jsonl')),
                    receipt=receipt)
        media.verify_receipt(path, receipt, 600,
            mapping_sha256=sha(required(attempt, 'video_frames.jsonl')))
        receipts[video] = sha(receipt)
    proof = {'format': 'worker-delivery-audit', 'passed': True,
        'case_id': args.case, 'job_id': args.job, 'attempt': args.attempt_number,
        'recording_id': args.recording_id, 'source_result_sha256': sha(result_path),
        'frames': 600, 'source_video_sha256': {name: sha(required(attempt, name)) for name in VIDEOS},
        'checks': {name: True for name in CHECKS}, 'auditor_sha256': sha(Path(__file__).resolve()),
        'source_decode_receipt_sha256': receipts,
        'human_review_sha256': sha(required(attempt, args.review)),
        'physical_observation': physical['observation'], 'legal_verdict_claimed': False}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
        'setup_confirmed': True, 'behavior_attempted': True, 'maneuver_completed': True,
        'accepted': False, 'legal_verdict_claimed': False,
        'measured_values': {'designated_place': {'source_hashes': {'device': 'sample'}},
                            'physical': {'status': 'met', 'frames': 600, 'legal_verdict_claimed': False}},
        'recording_evidence': [{'name': 'designated_place'}, {'name': 'person_activity_context'}]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for field, value in (('maneuver_completed', False), ('recording_evidence', []),
                         ('measured_values', {}), ('accepted', True)):
        changed = json.loads(json.dumps(sample))
        changed[field] = value
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Incomplete source accepted: ' + field)
    return {'case_id': case, 'source_predicates_tested': True,
            'original_capture_attested': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--operations')
    parser.add_argument('--output')
    parser.add_argument('--review', default='original-delivery-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args)))
