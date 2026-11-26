"""Independent original sidewalk encounter audit; CPU tests reject diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original source: exact Native sidewalk result')
    if result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original sidewalk pass incomplete')
    measured = result.get('measured_values', {})
    if (measured.get('rider_id') is None or measured.get('pedestrian_id') is None
            or not isinstance(measured.get('minimum_lateral_footprint_gap_m'), (int, float))):
        raise ValueError('Missing original source: rider and pedestrian measurements')
    if result.get('physical_acceptance_claimed') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Source finalizer preaccepted sidewalk outcome')
    if {row.get('name') for row in result.get('recording_evidence', [])} != {
            'rider_and_pedestrian_footprints', 'pedestrian_location_audio',
            'sidewalk_map_context', 'four_source_views'}:
        raise ValueError('Missing original sidewalk recording channels')


def check_review(review, case, paths):
    if (review.get('format') != 'c230266-original-sidewalk-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent sidewalk review')
    for name, path in paths.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Sidewalk review source changed: ' + name)
    for name in ('device_class_reviewed', 'sidewalk_context_reviewed',
                 'pedestrian_identity_reviewed', 'yield_response_reviewed',
                 'microphone_placement_reviewed', 'audible_signal_identity_reviewed',
                 'signal_before_pass_reviewed', 'actual_pixels_reviewed',
                 'physical_completion_reviewed'):
        if review.get(name) is not True:
            raise ValueError('Independent sidewalk review incomplete: ' + name)
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(frame) is not int or frame < 0 or frame >= 600 for frame in frames):
        raise ValueError('Decisive original pixel review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Review cannot prelabel legal outcome')


def audit(args):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime' /
                           'scenario_pipeline'))
    from worker_exchange import media

    attempt, output = Path(args.attempt).resolve(), Path(args.output).resolve()
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    paths = {'actors': source(attempt, 'sidewalk-actors.jsonl'),
             'cameras': source(attempt, 'camera-frames.jsonl'),
             'video_frames': source(attempt, 'video_frames.jsonl'),
             'microphone': source(attempt, 'pedestrian-microphone.json'),
             'microphone_frames': source(attempt, 'pedestrian-microphone-frames.jsonl'),
             'map': source(attempt, 'sidewalk-map-readback.json'),
             'road': source(attempt, 'road.xodr')}
    microphone = json.loads(paths['microphone'].read_text())
    paths['pcm'] = source(attempt, microphone['pcm_path'])
    check_review(json.loads(source(attempt, args.review).read_text()), args.case, paths)
    actors = [json.loads(line) for line in paths['actors'].read_text().splitlines()]
    cameras = [json.loads(line) for line in paths['cameras'].read_text().splitlines()]
    frames = [json.loads(line) for line in paths['video_frames'].read_text().splitlines()]
    audio_frames = [json.loads(line) for line in paths['microphone_frames'].read_text().splitlines()]
    if (len(actors), len(cameras), len(frames), len(audio_frames)) != (600, 2400, 600, 600):
        raise ValueError('Original sidewalk source frame count differs')
    if any(actors[i]['native_frame'] != frames[i]['native_frame'] or
           actors[i]['video_frame'] != i or frames[i]['video_frame'] != i
           for i in range(600)):
        raise ValueError('Original sidewalk/video frame join differs')
    for row in result['recording_evidence']:
        source(attempt, row['reference'])
    trace, video = source(attempt, args.trace), source(attempt, args.video)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(paths['video_frames']), receipt=decode)
    verified = media.verify_receipt(video, decode, 600,
                                    mapping_sha256=sha(paths['video_frames']))
    proof = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job,
             'attempt': args.attempt_number, 'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'frames': 600,
             'video_sha256': sha(video), 'trace_sha256': sha(trace),
             'checks': {name: True for name in CHECKS},
             'auditor_sha256': sha(Path(__file__).resolve()),
             'source_decode_receipt_sha256': sha(decode),
             'source_decode_auditor_sha256': verified['auditor_sha256'],
             'human_review_sha256': sha(source(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'behavior_attempted': True,
              'maneuver_completed': True, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False,
              'measured_values': {'minimum_lateral_footprint_gap_m': 1.0,
                                  'rider_id': 17, 'pedestrian_id': 19},
              'recording_evidence': [{'name': name} for name in
                  ('rider_and_pedestrian_footprints', 'pedestrian_location_audio',
                   'sidewalk_map_context', 'four_source_views')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic sidewalk source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('recording_evidence', []),
                       ('measured_values', {})):
        changed = {**sample, key: value}
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing original source accepted: ' + key)
    print(json.dumps({'case_id': case, 'selftest': 'passed'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--selftest', choices=('positive', 'negative'))
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    parser.add_argument('--review', default='independent-sidewalk-review.json')
    parser.add_argument('--trace', default='trace.jsonl')
    parser.add_argument('--video', default='raw.mkv')
    parser.add_argument('--job', default='unbound')
    parser.add_argument('--attempt-number', type=int, default=1)
    parser.add_argument('--recording-id', default='unbound')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.case, args.selftest == 'negative')
    elif args.attempt and args.output:
        print(json.dumps(audit(args)))
    else:
        parser.error('Need selftest or original attempt and output')
