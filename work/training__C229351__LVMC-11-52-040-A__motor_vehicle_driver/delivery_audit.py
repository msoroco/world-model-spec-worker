"""Independent original roadway-rest source audit and diagnostic rejection tests."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE / 'native'), str(ROOT / 'runtime/scenario_pipeline')]
from finalize import assess_rest

CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, relative):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + relative)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original source: exact original Native result')
    if (result.get('maneuver_completed') is not True or
            result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
        raise ValueError('Original roadway rest incomplete')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Source finalizer preaccepted legal outcome')
    if not {'drv.standing_or_parked', 'st.roadway', 'st.road_edge', 'kin.heading',
            'st.lane_direction', 'rel.occupies', 'st.parking_space'} <= {
                item.get('name') for item in result.get('recording_evidence', [])}:
        raise ValueError('Original selected observation channels absent')


def check_review(review, case, sources):
    if (review.get('format') != 'c229351-roadway-rest-original-review-v1' or
            review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Missing independent original roadway-rest review')
    for name, path in sources.items():
        if review.get(name + '_sha256') != sha(path):
            raise ValueError('Original review source changed: ' + name)
    required = ('roadway_edge_reviewed', 'lawful_direction_reviewed',
                'vehicle_body_reviewed', 'driver_identity_reviewed',
                'activity_purpose_reviewed', 'chapter_exception_reviewed',
                'actual_pixels_reviewed')
    if not all(review.get(name) is True for name in required):
        raise ValueError('Original roadway/activity/authority/pixels unreviewed')
    frames = review.get('reviewed_frames', [])
    if not frames or any(type(i) is not int or i < 0 or i >= 600 for i in frames):
        raise ValueError('Decisive original pixel frame review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Original review cannot prelabel legal outcome')


def audit(args):
    from worker_exchange import media
    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    operations = ROOT / 'state/operations/worker_exchange'
    if operations not in output.parents:
        raise ValueError('Independent audit output belongs in local operations')
    result_path = source(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    files = {'samples': 'native_samples.jsonl', 'bodies': 'body_history.jsonl',
             'frames': 'video_frames.jsonl', 'geometry': 'road_geometry.json',
             'survey': 'road_edge_survey.json', 'activity': 'activity_context.json'}
    sources = {key: source(attempt, value) for key, value in files.items()}
    check_review(json.loads(source(attempt, args.review).read_text()), args.case, sources)
    samples, bodies, mapping = rows(sources['samples']), rows(sources['bodies']), rows(sources['frames'])
    if any(len(data) != 600 for data in (samples, bodies, mapping)):
        raise ValueError('Original source frame count differs')
    if any(mapping[i]['video_frame'] != i or mapping[i]['native_frame'] != samples[i]['native_frame']
           for i in range(600)):
        raise ValueError('Original frame identities differ')
    geometry = json.loads(sources['geometry'].read_text())
    check = assess_rest(samples, bodies, geometry, {name: sha(path) for name, path in sources.items()})
    if check['status'] != 'met':
        raise ValueError('Independent roadway rest physical check failed')
    for entry in result['recording_evidence']:
        source(attempt, entry['reference'])
    trace = source(attempt, args.trace)
    video = source(attempt, args.video)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(sources['frames']), receipt=decode)
    verified = media.verify_receipt(video, decode, 600, mapping_sha256=sha(sources['frames']))
    proof = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job, 'attempt': args.attempt_number,
             'recording_id': args.recording_id, 'source_result_sha256': sha(result_path),
             'frames': 600, 'video_sha256': sha(video), 'trace_sha256': sha(trace),
             'checks': {name: True for name in CHECKS}, 'auditor_sha256': sha(Path(__file__).resolve()),
             'source_decode_receipt_sha256': sha(decode),
             'source_decode_auditor_sha256': verified['auditor_sha256'],
             'human_review_sha256': sha(source(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'maneuver_completed': True, 'physical_checks': {'maneuver': {'status': 'met'}},
              'accepted': False, 'legal_verdict_claimed': False,
              'recording_evidence': [{'name': name} for name in
                 ('drv.standing_or_parked', 'st.roadway', 'st.road_edge', 'kin.heading',
                  'st.lane_direction', 'rel.occupies', 'st.parking_space')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('maneuver_completed', False), ('recording_evidence', [])):
        changed = {**sample, key: value}
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Incomplete original source accepted: ' + key)
    return {'case_id': case, 'source_predicates_tested': True,
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
    parser.add_argument('--review', default='roadway-rest-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args)))
