"""Independent original-source pedestrian entry audit; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, rel):
    path = (root / rel).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + str(rel))
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') not in
            ('native', 'source_review_unverified') or result.get('diagnostic_fixture') is True):
        raise ValueError('Missing original source: exact original Native result')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Finalizer improperly preaccepted pedestrian outcome')
    measured = result.get('measured_values', {})
    if (type(measured.get('pedestrian_enters_highway')) is not bool or
            not isinstance(measured.get('potential_9c_entry_frames'), list)):
        raise ValueError('Missing source-bound pedestrian entry measurement')
    checks = result.get('target_checks', [])
    if not any(row.get('target') == 'pedestrian_enters_highway' and
               row.get('matched') is True and row.get('method') and row.get('cause_evidence')
               for row in checks):
        raise ValueError('Measured pedestrian branch did not physically match requested entry')
    if not result.get('realized_observables'):
        raise ValueError('Missing realized pedestrian motion observations')
    names = {row.get('name') for row in result.get('recording_evidence', [])}
    if not {'pedestrian_footprint', 'governing_red_and_turn_arrow',
            'other_device_permission', 'native_road_boundary',
            'governing_signal_authority', 'highway_authority'} <= names:
        raise ValueError('Original pedestrian, signal, exception or authority recording missing')


def check_review(review, frame_map, signal, device, boundary, governing, highway):
    if (review.get('format') != 'c228133-native-source-review-v1' or
            not review.get('reviewer') or review['reviewer'] == 'synthetic-cpu-fixture' or
            review.get('highway_boundary_basis') == 'synthetic_cpu_fixture' or
            review.get('highway_boundary_reviewed') is not True):
        raise ValueError('Missing independent original governing and highway review')
    sources = review.get('source_sha256', {})
    for name, path in (('native-signal-frames.jsonl', signal),
                       ('native-pedestrian-device-frames.jsonl', device),
                       ('video_frames.jsonl', frame_map), ('road-boundary.json', boundary),
                       ('governing-device-authority.json', governing),
                       ('highway-authority.json', highway)):
        if sources.get(name) != sha(path):
            raise ValueError('Original source review hash differs: ' + name)
    decisions = review.get('frames', [])
    if len(decisions) != 600 or any(
            not row.get('directional_arrow_pixels_reviewed') or
            not row.get('facing_governance_reviewed') or
            not row.get('other_device_inventory_reviewed') or
            set(row.get('source_rgb_sha256', {})) != set(VIEWS)
            for row in decisions):
        raise ValueError('Original indication, exception or pixel review incomplete')


def check_join(frame_map, trace):
    frames = [json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes = json.loads(trace.read_text()).get('scenes', [])
    if len(frames) != 600 or len(scenes) != 600:
        raise ValueError('Original frame/Core count mismatch')
    for index, (frame, scene) in enumerate(zip(frames, scenes)):
        if frame.get('video_frame') != index or scene.get('t') != round(frame['time_s'] * 1000):
            raise ValueError('Original frame/Core timestamp mismatch')
    return len(frames)


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent auditor must run inside local operations')
    result_path = inside(attempt, 'result.json')
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    provenance = json.loads(inside(attempt, 'acquisition-provenance.json').read_text())
    if (provenance.get('provenance_kind') != 'native' or
            provenance.get('native_executed') is not True or
            provenance.get('diagnostic_fixture') is True):
        raise ValueError('Original Native acquisition provenance missing')
    frame_map = inside(attempt, 'video_frames.jsonl')
    signal = inside(attempt, 'native-signal-frames.jsonl')
    device = inside(attempt, 'native-pedestrian-device-frames.jsonl')
    boundary = inside(attempt, 'road-boundary.json')
    governing = inside(attempt, 'governing-device-authority.json')
    highway = inside(attempt, 'highway-authority.json')
    review = inside(attempt, args.review)
    check_review(json.loads(review.read_text()), frame_map, signal, device,
                 boundary, governing, highway)
    for row in result['recording_evidence']:
        inside(attempt, row['reference'])
    trace = inside(attempt, args.trace)
    video = inside(attempt, args.video)
    frames = check_join(frame_map, trace)
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, frames, mapping_sha256=sha(frame_map), receipt=decode)
    verified = media.verify_receipt(video, decode, frames, mapping_sha256=sha(frame_map))
    payload = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': args.case,
               'job_id': args.job, 'attempt': args.attempt_number,
               'recording_id': args.recording_id,
               'source_result_sha256': sha(result_path), 'frames': frames,
               'video': args.video, 'video_sha256': sha(video),
               'trace': args.trace, 'trace_sha256': sha(trace),
               'checks': {name: True for name in CHECKS},
               'auditor_path': str(Path(__file__).resolve()),
               'auditor_sha256': sha(Path(__file__).resolve()),
               'source_decode_receipt_path': str(decode),
               'source_decode_receipt_sha256': sha(decode),
               'source_decode_auditor_sha256': verified['auditor_sha256'],
               'human_review_sha256': sha(review),
               'physical_acceptance_claimed_by_fixture': False}
    output.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'source_review_unverified',
              'accepted': False, 'legal_verdict_claimed': False,
              'realized_observables': {'highway_entry_event_count': {'value': 1, 'unit': 'count'}},
              'measured_values': {'pedestrian_enters_highway': case.endswith('__contrast'),
                                  'potential_9c_entry_frames': [80] if case.endswith('__contrast') else []},
              'target_checks': [{'target': 'pedestrian_enters_highway', 'matched': True,
                                 'method': 'original source review',
                                 'cause_evidence': ['native-pedestrian-frames.jsonl']}],
              'recording_evidence': [{'name': name} for name in
                  ('pedestrian_footprint', 'governing_red_and_turn_arrow',
                   'other_device_permission', 'native_road_boundary',
                   'governing_signal_authority', 'highway_authority')]}
    if negative:
        sample['provenance_kind'] = 'synthetic_local_diagnostic'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key, value in (('target_checks', []), ('realized_observables', {})):
        changed = json.loads(json.dumps(sample))
        changed[key] = value
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing physical source accepted')
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
    parser.add_argument('--review', default='independent-review.json')
    parser.add_argument('--job', type=int)
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    arguments = parser.parse_args()
    print(json.dumps(selftest(arguments.case, arguments.negative) if arguments.self_test else audit(arguments), indent=2))
