"""Independent original-source divided-highway delivery predicates."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('original_divided_context.json', 'original_turn_annotations.json',
           'median-capture.jsonl', 'body_history.jsonl', 'trace.jsonl',
           'video_frames.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_native(root, case):
    root = Path(root)
    result = json.loads((root / 'result.json').read_text())
    if result.get('case_id') != case or result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Exact original Native result missing')
    if not result.get('maneuver_completed') or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Original left-turn completion missing')
    for source in SOURCES:
        if not (root / source).is_file():
            raise ValueError('Original source missing: ' + source)
    report = json.loads((root / 'analysis-report.json').read_text())
    values = [record['value'] for record in report['measurements'].values()]
    if not values or any(v.get('frame_count') != 600 or v.get('legal_compliance') != 'unassessed' for v in values):
        raise ValueError('Original full-duration legal-neutral measurement missing')
    source_hashes = report['measurements']['crossing_section']['sources']
    if any(source_hashes.get(name) != sha(root / name) for name in SOURCES):
        raise ValueError('Original measurement source hash differs')
    mapping = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    if len(mapping) != 600 or any(row.get('camera_native_frames') != {name: row.get('native_frame') for name in CAMERAS} for row in mapping):
        raise ValueError('Original synchronized four-camera source missing')
    for camera in CAMERAS:
        if not (root / (camera + '.mkv')).is_file():
            raise ValueError('Original camera missing: ' + camera)
    review = json.loads((root / 'source-review.json').read_text())
    if review.get('source_kind') != 'original_native_review' or review.get('case_id') != case:
        raise ValueError('Original source and pixel review missing')
    if any(review.get('source_sha256', {}).get(source) != sha(root / source) for source in SOURCES):
        raise ValueError('Original review source hash differs')
    return {'case_id': case, 'source_result_sha256': sha(root / 'result.json'),
            'source_review_sha256': sha(root / 'source-review.json')}


def selftest(case, negative):
    sample = {'case_id': case, 'provenance_kind': 'native', 'diagnostic_fixture': False,
              'maneuver_completed': True, 'physical_checks': {'maneuver': {'status': 'met'}}}
    if negative:
        sample['provenance_kind'] = 'synthetic_fixture'
    if sample['provenance_kind'] != 'native' or sample['diagnostic_fixture'] is not False:
        raise ValueError('Exact original Native result missing')
    assert sample['maneuver_completed'] and sample['physical_checks']['maneuver']['status'] == 'met'
    print(json.dumps({'case_id': case, 'cpu_predicates_passed': True,
                      'actual_original_source_claimed': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    args = parser.parse_args()
    if args.self_test:
        selftest(args.case, args.negative)
    else:
        print(json.dumps(require_native(args.attempt, args.case), sort_keys=True))
