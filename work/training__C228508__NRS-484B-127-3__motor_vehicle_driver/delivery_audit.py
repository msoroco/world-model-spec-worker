"""Independent future original-capture audit for caravan spacing deliveries."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('authored-context.json', 'native_samples.jsonl',
           'native-source-inventory.json', 'video_frames.jsonl', 'trace.jsonl',
           'caravan_history.jsonl')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def source(root, name):
    path = (root / name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: ' + name)
    return path


def check_result(result, case):
    if (result.get('case_id') != case or result.get('provenance_kind') != 'native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Exact original Native result missing')
    metric = result.get('measured_values', {})
    if set(metric.get('source_sha256', {})) != set(SOURCES):
        raise ValueError('Original source inventory incomplete')
    if (not result.get('maneuver_completed') or
            result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
        raise ValueError('Original caravan entry completion missing')
    if metric.get('legal_sufficiency_judgment') is not None:
        raise ValueError('Automated legal sufficiency verdict prohibited')
    return metric


def audit(args):
    attempt = Path(args.attempt).resolve()
    result_path = source(attempt, 'result.json')
    result = load(result_path)
    metric = check_result(result, args.case)
    seal = load(source(attempt, 'capture-seal.json'))
    if seal.get('format') != 'worker-sealed-capture' or seal.get('diagnostic_fixture'):
        raise ValueError('Original Native capture seal missing')
    for name, digest in metric['source_sha256'].items():
        if sha(source(attempt, name)) != digest:
            raise ValueError('Original source hash differs: ' + name)
    mapping = lines(source(attempt, 'video_frames.jsonl'))
    actors = lines(source(attempt, 'native_samples.jsonl'))
    if len(mapping) != 600 or len(actors) != 600:
        raise ValueError('Original full-duration participant history missing')
    for index, (frame, row) in enumerate(zip(mapping, actors)):
        if (frame.get('video_frame') != index or frame.get('carla_frame') != row.get('native_frame')
                or abs(frame['time_s'] - row['time_s']) > 1e-6):
            raise ValueError('Original frame/time join differs')
        if set(row.get('actors', {})) != {'lead', 'ego_combination', 'trailer_proxy',
                                        'rear', 'potential_entrant'}:
            raise ValueError('Original complete participant inventory missing')
    review = load(source(attempt, args.review))
    required = ('highway_outside_business_district', 'caravan_membership',
                'vehicle_or_combination_identity', 'entry_without_danger',
                'four_camera_actual_pixels', 'physical_maneuver')
    if (review.get('case_id') != args.case or not review.get('reviewer_id')
            or review.get('source_kind') != 'original_native_review'
            or any(review.get('findings', {}).get(key) is not True for key in required)
            or review.get('result_sha256') != sha(result_path)
            or review.get('frame_map_sha256') != sha(attempt / 'video_frames.jsonl')):
        raise ValueError('Independent original source and safety review missing')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime/scenario_pipeline'))
    from worker_exchange import media
    for name in CAMERAS:
        video = source(attempt, name + '.mkv')
        media.audit(video, 600, mapping_sha256=sha(attempt / 'video_frames.jsonl'))
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError('Retain previous independent audit')
    output.parent.mkdir(parents=True, exist_ok=True)
    value = {'format':'worker-delivery-audit','case_id':args.case,
             'job_id':args.job,'recording_id':args.recording_id,'passed':True,
             'checks':{key:True for key in CHECKS},
             'result_sha256':sha(result_path),'review_sha256':sha(attempt / args.review),
             'physical_or_legal_acceptance_claimed_by_fixture':False}
    output.write_text(json.dumps(value, indent=2) + '\n')
    return value


def selftest(case, negative):
    sample = {'case_id':case,'provenance_kind':'native','diagnostic_fixture':False,
              'measured_values':{'source_sha256':{name:'0'*64 for name in SOURCES},
                                 'legal_sufficiency_judgment':None},
              'maneuver_completed':True,
              'physical_checks':{'maneuver':{'status':'met'}}}
    if negative:
        sample['diagnostic_fixture'] = True
        check_result(sample, case)
        raise AssertionError('Synthetic fixture accepted as original Native')
    check_result(sample, case)
    for name in SOURCES:
        damaged = json.loads(json.dumps(sample))
        damaged['measured_values']['source_sha256'].pop(name)
        try:
            check_result(damaged, case)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing original source accepted: ' + name)
    print(json.dumps({'case_id':case,'cpu_predicates_passed':True,
                      'original_native_execution_claimed':False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    for name in ('attempt','review','output','job','recording-id'):
        parser.add_argument('--' + name)
    options = parser.parse_args()
    if options.self_test:
        selftest(options.case, options.negative)
    else:
        print(json.dumps(audit(options)))
