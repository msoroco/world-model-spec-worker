"""Independently audit original intersection entry sources and saved delivery."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('actor-history.json', 'road-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'crossing_history.jsonl', 'capture/evidence.jsonl')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def source(root, name):
    path = (root / name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is True):
        raise ValueError('Exact original Native result missing')
    metric = result.get('measured_values', {})
    if (metric.get('frames') != 600 or
            metric.get('priority_entered_first_measured') is not True or
            metric.get('right_of_way_legally_determined') is not False or
            metric.get('official_device_governance_verified') is not False):
        raise ValueError('Original priority measurement or unresolved context missing')
    if case.endswith('__priority_yield') and metric.get('priority_present_at_ego_entry') is not False:
        raise ValueError('Yield case did not wait for priority vehicle to clear')
    if case.endswith('__priority_intrusion') and metric.get('priority_present_at_ego_entry') is not True:
        raise ValueError('Intrusion case lacks overlapping intersection occupancy')
    if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original physical traversal unproven')
    return metric


def check_review(review, case, attempt, metric):
    if (review.get('format') != 'c111294-2501-original-review-v1' or
            review.get('source_kind') != 'original_native_review' or
            review.get('case_id') != case or not review.get('reviewer_id')):
        raise ValueError('Original pixel and source review missing')
    for key in ('different_highway_other_visible', 'yield_sequence_visible',
                'official_device_governance_reviewed',
                'opposite_direction_left_turn_exclusion_reviewed',
                'subsection4_reviewed'):
        if type(review.get(key)) is not bool:
            raise ValueError('Original review finding missing: ' + key)
    if review['different_highway_other_visible'] is not True or review['yield_sequence_visible'] is not True:
        raise ValueError('Original participant or entry sequence not visible')
    media = review.get('media_sha256', {})
    if set(media) != {name + '.mkv' for name in (*CAMERAS, 'raw')}:
        raise ValueError('Original camera inventory incomplete')
    if any(sha(source(attempt, name)) != digest for name, digest in media.items()):
        raise ValueError('Original video hash differs')
    if (review.get('video_frames_sha256') != sha(source(attempt, 'video_frames.jsonl')) or
            review.get('raw_sha256') != sha(source(attempt, 'native-raw-actors.jsonl'))):
        raise ValueError('Original frame or actor review binding differs')
    if metric['right_of_way_legally_determined'] is not False:
        raise ValueError('Legal judgment was prematurely resolved')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt, output = Path(args.attempt).resolve(), Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain prior independent audit')
    result_path = source(attempt, 'result.json')
    metric = check_result(read(result_path), args.case)
    for name in SOURCES:
        source(attempt, name)
    rows = [json.loads(line) for line in source(attempt, 'video_frames.jsonl').read_text().splitlines()]
    actor = read(source(attempt, 'actor-history.json'))
    bodies = [json.loads(line) for line in source(attempt, 'crossing_history.jsonl').read_text().splitlines()]
    if (len(rows) != 600 or len(actor.get('rows', [])) != 600 or len(bodies) != 600 or
            any(row.get('video_frame') != i or row.get('camera_native_frames') !=
                {name: row.get('native_frame') for name in CAMERAS}
                for i, row in enumerate(rows)) or
            any(body.get('ego_vertices_m') != actors['ego']['body_xyz_m'] or
                body.get('other_vertices_m') != actors['other']['body_xyz_m']
                for body, actors in zip(bodies, actor['rows']))):
        raise ValueError('Original frame or full-body participant join differs')
    review_path = source(attempt, args.review)
    check_review(read(review_path), args.case, attempt, metric)
    video = source(attempt, args.video)
    mapping = source(attempt, 'video_frames.jsonl')
    decode = output.with_name('source-decode-' + args.case.rsplit('__', 1)[-1] + '.json')
    media.audit(video, 600, mapping_sha256=sha(mapping), receipt=decode)
    media.verify_receipt(video, decode, 600, mapping_sha256=sha(mapping))
    trace = source(attempt, args.trace)
    scenes = read(trace).get('scenes', [])
    if len(scenes) != 600 or any(scene.get('t') != round(row['time_s'] * 1000)
                                 for scene, row in zip(scenes, rows)):
        raise ValueError('Core and original frame time join differs')
    value = {'format': 'worker-delivery-audit', 'passed': True,
             'case_id': args.case, 'job_id': args.job,
             'recording_id': args.recording_id,
             'source_result_sha256': sha(result_path), 'video_sha256': sha(video),
             'trace_sha256': sha(trace), 'human_review_sha256': sha(review_path),
             'checks': {name: True for name in CHECKS},
             'physical_or_legal_acceptance_claimed_by_fixture': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + '\n')
    return value


def selftest(case, negative):
    metric = {'frames': 600, 'priority_entered_first_measured': True,
              'priority_present_at_ego_entry': case.endswith('__priority_intrusion'),
              'right_of_way_legally_determined': False,
              'official_device_governance_verified': False}
    sample = {'case_id': case, 'provenance_kind': 'native',
              'diagnostic_fixture': False, 'measured_values': metric,
              'maneuver_completed': True,
              'physical_checks': {'maneuver': {'status': 'met'}}}
    if negative:
        sample['provenance_kind'] = 'synthetic_local_diagnostic'
        check_result(sample, case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample, case)
    for key in ('priority_entered_first_measured', 'priority_present_at_ego_entry'):
        changed = json.loads(json.dumps(sample))
        changed['measured_values'].pop(key)
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing measured priority source accepted: ' + key)
    print(json.dumps({'case_id': case, 'cpu_predicates_passed': True,
                      'original_acquisition_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    for name in ('attempt', 'output', 'video', 'trace', 'review', 'job', 'recording-id'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    selftest(args.case, args.negative) if args.self_test else audit(args)
