"""Independent original-source review gate for governing-law contrast cases."""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing original sidewalk source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original sidewalk source: exact Native result')
    if result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original sidewalk stop motion incomplete')
    measured = result.get('measured_values', {})
    if (not isinstance(measured.get('rest_frames'), int) or
            not isinstance(measured.get('rest_and_overlap_frames'), int) or
            measured.get('actor_id') is None or
            not isinstance(measured.get('governing_law_context'), dict)):
        raise ValueError('Missing original sidewalk or law source measurements')
    if result.get('physical_acceptance_claimed') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Selected finalizer preaccepted sidewalk outcome')
    required = {'vehicle_body_pose', 'vehicle_speed', 'sidewalk_overlap',
                'sidewalk_map_context', 'exception_authority_context',
                'governing_law_context'}
    if not required <= {row.get('name') for row in result.get('recording_evidence', [])}:
        raise ValueError('Missing original sidewalk recording channels')


def check_packet(packet, case, law_text=None):
    present = case.endswith('_present')
    if (packet.get('case_id') != case or packet.get('authority_kind') != 'law'
            or packet.get('requested_presence') != present
            or packet.get('legal_conclusion') is not None
            or packet.get('compliance_independently_verified') is not False):
        raise ValueError('Unbound or preclaimed original governing-law packet')
    binding = packet.get('authority_binding')
    if not present:
        if binding is not None:
            raise ValueError('Absent case contains law authority')
    else:
        if (not isinstance(binding, dict) or not binding.get('law_citation')
                or binding.get('law_text_source') != 'specific-law.txt'
                or law_text is None or binding.get('law_text_sha256') != sha(law_text)
                or not binding.get('scope_review')):
            raise ValueError('Missing source-bound specific governing law')


def check_review(review, case, paths):
    if (review.get('format') != 'c229977-original-law-review-v1'
            or review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent sidewalk law review')
    for name, path in paths.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Sidewalk law review source changed: ' + name)
    required = ('sidewalk_surface_source_reviewed', 'vehicle_body_reviewed',
                'stop_interval_reviewed', 'exception_authority_reviewed',
                'specific_law_identity_reviewed', 'actor_applicability_reviewed',
                'temporal_compliance_reviewed', 'actual_pixels_reviewed',
                'physical_completion_reviewed')
    if any(review.get(name) is not True for name in required):
        raise ValueError('Independent sidewalk law review incomplete')
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(frame) is not int or frame < 0 or frame >= 600 for frame in frames):
        raise ValueError('Decisive original pixel review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Review cannot prelabel legal outcome')


def check_frames(trace, cameras, frames):
    if len(trace) != 600 or len(frames) != 600 or len(cameras) != 2400:
        raise ValueError('Original sidewalk/video frame count differs')
    if any(trace[i].get('frame') != frames[i].get('video_frame') or
           trace[i].get('native_frame') != frames[i].get('native_frame') or
           abs(float(trace[i]['time_s']) - float(frames[i]['time_s'])) > 1e-4
           for i in range(600)):
        raise ValueError('Original sidewalk/video frame join differs')
    found = {(row.get('frame'), row.get('camera'), row.get('native_frame'))
             for row in cameras}
    expected = {(i, name, frames[i]['native_frame'])
                for i in range(600) for name in CAMERAS}
    if found != expected:
        raise ValueError('Original camera/video frame join differs')


def audit(args):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'))
    from worker_exchange import media

    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    paths = {'vehicle_trace': source(attempt, 'vehicle-trace.jsonl'),
             'cameras': source(attempt, 'camera-frames.jsonl'),
             'video_frames': source(attempt, 'video_frames.jsonl'),
             'map_packet': source(attempt, 'map-packet.json'),
             'authority_context': source(attempt, 'authority-context.json'),
             'law_authority': source(attempt, 'law-authority.json'),
             'road': source(attempt, 'native-road.xodr')}
    if args.case.endswith('_present'):
        paths['specific_law'] = source(attempt, 'specific-law.txt')
    packet = json.loads(paths['law_authority'].read_text())
    check_packet(packet, args.case, paths.get('specific_law'))
    check_review(json.loads(source(attempt, args.review).read_text()), args.case, paths)
    trace = [json.loads(line) for line in paths['vehicle_trace'].read_text().splitlines()]
    cameras = [json.loads(line) for line in paths['cameras'].read_text().splitlines()]
    frames = [json.loads(line) for line in paths['video_frames'].read_text().splitlines()]
    check_frames(trace, cameras, frames)
    for row in result['recording_evidence']:
        source(attempt, row['reference'])
    converted = source(attempt, args.trace)
    video = source(attempt, args.video)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(paths['video_frames']), receipt=decode)
    verified = media.verify_receipt(video, decode, 600,
                                    mapping_sha256=sha(paths['video_frames']))
    proof = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job,
             'attempt': args.attempt_number, 'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'frames': 600,
             'video_sha256': sha(video), 'trace_sha256': sha(converted),
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
              'measured_values': {'rest_frames': 200,
                                  'rest_and_overlap_frames': 100,
                                  'governing_law_context': {}, 'actor_id': 107},
              'recording_evidence': [{'name': name} for name in (
                  'vehicle_body_pose', 'vehicle_speed', 'sidewalk_overlap',
                  'sidewalk_map_context', 'exception_authority_context',
                  'governing_law_context')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('recording_evidence', []),
                       ('measured_values', {})):
        try:
            check_result({**sample, key: value}, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing original source accepted: ' + key)
    frames = [{'native_frame': i + 1, 'video_frame': i, 'time_s': i / 20}
              for i in range(600)]
    trace = [{'native_frame': i + 1, 'frame': i, 'time_s': i / 20}
             for i in range(600)]
    cameras = [{'frame': i, 'camera': name, 'native_frame': i + 1}
               for i in range(600) for name in sorted(CAMERAS)]
    check_frames(trace, cameras, frames)
    changed = [dict(row) for row in trace]
    changed[300]['native_frame'] += 1
    try:
        check_frames(changed, cameras, frames)
    except ValueError:
        pass
    else:
        raise AssertionError('Unjoined vehicle frame accepted')
    scratch = Path('.runtime-work')
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='c229977-law-audit-', dir=scratch) as folder:
        root = Path(folder)
        original = root / 'original-source.json'
        original.write_text('{}\n')
        paths = {'law_authority': original}
        review = {'format': 'c229977-original-law-review-v1',
                  'case_id': case, 'reviewer_id': 'diagnostic-reviewer',
                  'law_authority_sha256': sha(original),
                  'reviewed_frames': [300], 'legal_verdict_claimed': False}
        for name in ('sidewalk_surface_source_reviewed', 'vehicle_body_reviewed',
                     'stop_interval_reviewed', 'exception_authority_reviewed',
                     'specific_law_identity_reviewed', 'actor_applicability_reviewed',
                     'temporal_compliance_reviewed', 'actual_pixels_reviewed',
                     'physical_completion_reviewed'):
            review[name] = True
        check_review(review, case, paths)
        for changed in ({**review, 'actor_applicability_reviewed': False},
                        {**review, 'reviewed_frames': []},
                        {**review, 'law_authority_sha256': '0' * 64},
                        {**review, 'legal_verdict_claimed': True}):
            try:
                check_review(changed, case, paths)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid independent review accepted')
        original.write_text('{"changed":true}\n')
        try:
            check_review(review, case, paths)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed original law source accepted')
    return {'case_id': case, 'source_predicates_tested': True,
            'frame_join_tested': True, 'review_source_binding_tested': True,
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
    parser.add_argument('--review', default='law-original-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative)
                     if args.self_test else audit(args)))
