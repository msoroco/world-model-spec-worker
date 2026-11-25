"""Independent original-source delivery audit for NRS 484D.100(1)(c).

The CPU self-test exercises predicates only. Local acceptance needs an original
Native attempt, independent pixel review and full media decode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def inside(root, rel):
    path = (root / rel).resolve()
    require(root.resolve() in path.parents and path.is_file(),
            'Missing original source: ' + str(rel))
    return path


def check_result(result, case):
    require(result.get('case_id') == case and
            result.get('provenance_kind') == 'native_saved_sample' and
            result.get('diagnostic_fixture') is False,
            'Missing original source: exact Native result')
    require(result.get('accepted') is False and
            result.get('legal_verdict_claimed') is False,
            'Finalizer preaccepted legal or physical outcome')
    measured = result.get('measured_values', {})
    require(measured.get('source_kind') == 'native_saved_sample' and
            measured.get('frame_count') == 600 and
            len(measured.get('governed_frames', [])) >= 200 and
            len(measured.get('moving_frames', [])) >= 400,
            'Missing original source-bound governed travel')
    checks = result.get('target_checks', [])
    require(len(checks) == 1 and checks[0].get('matched') is True and
            checks[0].get('physical_cause_confirmed') is False,
            'Lamp setting target/source proof missing')
    require(set(result.get('video_references', [])) ==
            {camera + '.mkv' for camera in CAMERAS},
            'Four original video references missing')
    return measured


def check_join(frame_rows, lamp_rows, measured):
    require(len(frame_rows) == len(lamp_rows) == 600,
            'Original lamp/frame count mismatch')
    for index, (frame, lamp) in enumerate(zip(frame_rows, lamp_rows)):
        require(frame.get('video_frame') == lamp.get('video_frame') == index and
                frame.get('native_frame') == lamp.get('native_frame') and
                frame.get('camera_native_frames') == lamp.get('camera_native_frames') and
                abs(frame['time_s'] - lamp['time_s']) < 1e-8,
                'Original lamp/frame time join mismatch')
        require(set(frame.get('camera_native_frames', {})) == set(CAMERAS),
                'Four source cameras not synchronized')
    require(measured.get('frame_count') == len(frame_rows),
            'Measured count differs from original')
    return len(frame_rows)


def check_review(review, case, source_hashes, measured):
    require(review.get('format') == 'c179824-original-lamp-pixel-review-v1' and
            review.get('source_kind') == 'original_native_review' and
            review.get('case_id') == case and review.get('reviewer_id'),
            'Missing independent original lamp pixel review')
    for field, digest in source_hashes.items():
        require(review.get(field) == digest,
                'Original pixel review source hash changed: ' + field)
    require(review.get('native_actor_identity_verified') is True and
            review.get('official_device_source_verified') is True and
            review.get('public_highway_source_verified') is True and
            review.get('travel_completed_from_original') is True,
            'Independent Native setup or travel review missing')
    frames = review.get('reviewed_frames', [])
    governed = set(measured['governed_frames'])
    require(isinstance(frames, list) and len(frames) >= 3 and
            all(type(f) is int and f in governed for f in frames),
            'Missing reviewed original governed pixels')
    require(set(review.get('reviewed_cameras', [])) == set(CAMERAS),
            'Original camera pixel coverage incomplete')
    expected_on = case.endswith('__controlled_1')
    require(review.get('observed_lamp_emission_on') is expected_on,
            'Independent original lamp pixels differ from selected setting')
    require(review.get('class_equipment_sufficiency_claimed') is False and
            review.get('legal_verdict_claimed') is False,
            'Pixel review improperly claimed legal sufficiency')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt, operations, output = (Path(args.attempt).resolve(),
                                   Path(args.operations).resolve(),
                                   Path(args.output).resolve())
    require(operations in Path(__file__).resolve().parents and operations in output.parents,
            'Independent auditor must run inside local operations')
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    measured = check_result(result, args.case)
    frame_path = inside(attempt, 'video_frames.jsonl')
    lamp_path = inside(attempt, 'vehicle-lamps.jsonl')
    context_path = inside(attempt, 'lamp-context.json')
    review_path = inside(attempt, args.review)
    frame_rows = [json.loads(line) for line in frame_path.read_text().splitlines()]
    lamp_rows = [json.loads(line) for line in lamp_path.read_text().splitlines()]
    frames = check_join(frame_rows, lamp_rows, measured)
    for row in result.get('recording_evidence', []):
        inside(attempt, row['reference'])
    video = inside(attempt, args.video)
    trace = inside(attempt, args.trace)
    source_hashes = {'result_sha256': sha(result_path),
                     'frame_map_sha256': sha(frame_path),
                     'lamp_trace_sha256': sha(lamp_path),
                     'lamp_context_sha256': sha(context_path),
                     'video_sha256': sha(video)}
    check_review(json.loads(review_path.read_text()), args.case, source_hashes, measured)
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, frames, mapping_sha256=sha(frame_path), receipt=decode)
    verified = media.verify_receipt(video, decode, frames,
                                    mapping_sha256=sha(frame_path))
    payload = {'format': 'worker-delivery-audit', 'passed': True,
               'case_id': args.case, 'job_id': args.job,
               'attempt': args.attempt_number, 'recording_id': args.recording_id,
               'source_result_sha256': sha(result_path), 'frames': frames,
               'video': args.video, 'video_sha256': sha(video),
               'trace': args.trace, 'trace_sha256': sha(trace),
               'checks': {name: True for name in CHECKS},
               'auditor_path': str(Path(__file__).resolve()),
               'auditor_sha256': sha(Path(__file__).resolve()),
               'source_decode_receipt_path': str(decode),
               'source_decode_receipt_sha256': sha(decode),
               'source_decode_auditor_sha256': verified['auditor_sha256'],
               'human_review_sha256': sha(review_path)}
    output.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def self_test(case, negative):
    original = {'case_id': case, 'provenance_kind': 'native_saved_sample',
                'diagnostic_fixture': False, 'accepted': False,
                'legal_verdict_claimed': False,
                'measured_values': {'source_kind': 'native_saved_sample',
                                    'frame_count': 600,
                                    'governed_frames': list(range(200, 600)),
                                    'moving_frames': list(range(600))},
                'target_checks': [{'matched': True,
                                   'physical_cause_confirmed': False}],
                'video_references': [camera + '.mkv' for camera in CAMERAS]}
    measured = check_result(original, case)
    source_hashes = {name: hashlib.sha256(name.encode()).hexdigest() for name in
                     ('result_sha256', 'frame_map_sha256', 'lamp_trace_sha256',
                      'lamp_context_sha256', 'video_sha256')}
    review = {'format': 'c179824-original-lamp-pixel-review-v1',
              'source_kind': 'original_native_review', 'case_id': case,
              'reviewer_id': 'cpu-predicate-fixture',
              'native_actor_identity_verified': True,
              'official_device_source_verified': True,
              'public_highway_source_verified': True,
              'travel_completed_from_original': True,
              'reviewed_frames': [200, 300, 400],
              'reviewed_cameras': list(CAMERAS),
              'observed_lamp_emission_on': case.endswith('__controlled_1'),
              'class_equipment_sufficiency_claimed': False,
              'legal_verdict_claimed': False, **source_hashes}
    if negative:
        review.pop('video_sha256')
        check_review(review, case, source_hashes, measured)
        raise AssertionError('Missing source passed')
    check_review(review, case, source_hashes, measured)
    for change in ('synthetic', 'missing_pixels', 'wrong_lamp'):
        bad = json.loads(json.dumps(original if change == 'synthetic' else review))
        if change == 'synthetic':
            bad['provenance_kind'] = 'synthetic_native_sample'
            fn = lambda: check_result(bad, case)
        else:
            if change == 'missing_pixels':
                bad['reviewed_frames'] = []
            else:
                bad['observed_lamp_emission_on'] = not bad['observed_lamp_emission_on']
            fn = lambda: check_review(bad, case, source_hashes, measured)
        try:
            fn()
        except ValueError:
            pass
        else:
            raise AssertionError('Damaged original source passed: ' + change)
    return {'case_id': case, 'source_predicates_tested': True,
            'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--operations')
    parser.add_argument('--output')
    parser.add_argument('--trace', default='converted/trace.json')
    parser.add_argument('--video', default='primary.mkv')
    parser.add_argument('--review', default='lamp-pixel-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(self_test(args.case, args.negative) if args.self_test else audit(args),
                     indent=2))
