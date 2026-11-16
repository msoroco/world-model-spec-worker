"""CPU unit proof of the original-delivery audit branch.

All files and motion results here are mocked in a temporary directory. They are
never returned as a Native capture or an accepted recording.
"""
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import audit_delivery


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def fixture(root, case):
    attempt = root / 'mock-attempt'
    attempt.mkdir()
    hashes = {}
    for source in audit_delivery.SOURCES:
        path = attempt / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('CPU mock source: ' + source + '\n').encode())
        hashes[source] = digest(path)
    report = {'case_id': case, 'candidate_id': 'primary', 'observed_frames': 240,
              'error': None, 'closure_failures': [],
              'lifecycle_events': ['capture_finished', 'encoders_closed',
                                   'restoration_verified'],
              'restoration': {'restored': True}}
    write_json(attempt / 'native-capture-report.json', report)
    saved = root / 'mock-saved'
    result_path = saved / 'v0001' / 'result.json'
    write_json(result_path, {'case_id': case, 'accepted': False,
                             'provenance_kind': 'native',
                             'maneuver_completed': True})
    views = {}
    subjects = ('ego_body', 'lead_body', 'right_lane', 'roadway')
    for index, camera in enumerate(audit_delivery.CAMERAS):
        rgb = hashlib.sha256(('mock RGB ' + camera).encode()).hexdigest()
        write_json(saved / f'source-{index}.json',
                   {'passed': True, 'frames': 240,
                    'video_sha256': hashes[camera + '.mkv'],
                    'rgb_sequence_sha256': rgb})
        views[camera] = {'video_sha256': hashes[camera + '.mkv'],
                         'reviewed_frame_ids': list(range(240)),
                         'rgb_sequence_sha256': rgb, 'limitations': [],
                         'subjects_visible': list(subjects) if index == 0 else []}
    review_path = root / 'mock-pixel-review.json'
    write_json(review_path, {'format': 'c146314-original-pixel-review-v1',
                              'case_id': case,
                              'source_kind': 'original_native_camera_pixels',
                              'reviewer': 'CPU mock reviewer',
                              'method': 'CPU mock contract input',
                              'frame_map_sha256': hashes['video_frames.jsonl'],
                              'legal_verdict_claimed': False, 'views': views})
    processing = {'case_id': case, 'candidate_id': 'primary', 'passed': True,
                  'recorded_only': True, 'originals_preserved': True,
                  'missing_evidence': False, 'original_source_hashes': hashes,
                  'timestamp_joins': {'passed': True, 'frames': 240},
                  'final_video_checks': {'passed': True, 'frames': 240},
                  'result': str(result_path), 'result_sha256': digest(result_path)}
    return attempt, processing, review_path


def run(case):
    with tempfile.TemporaryDirectory(prefix='c146314-delivery-contract-') as tmp:
        attempt, processing, review = fixture(Path(tmp), case)
        measured = {'source_kind': 'original_native', 'status': 'met'}
        with patch.object(audit_delivery, 'audit_motion', return_value=measured):
            positive = audit_delivery.audit(attempt, processing, case, 'primary', review)
            assert positive['passed'] and positive['delivery_accepted']
            assert all(positive['checks'].values())
            failures = {}

            def reject(label, action, expected):
                try:
                    action()
                except ValueError as error:
                    assert expected in str(error), (label, str(error))
                    failures[label] = str(error)
                else:
                    raise AssertionError('CPU mock negative accepted: ' + label)

            changed = copy.deepcopy(processing)
            changed['original_source_hashes']['native-raw-actors.jsonl'] = '0' * 64
            reject('changed_source', lambda: audit_delivery.audit(
                attempt, changed, case, 'primary', review), 'Original delivery sources changed')
            changed = copy.deepcopy(processing)
            changed['timestamp_joins']['passed'] = False
            reject('broken_join', lambda: audit_delivery.audit(
                attempt, changed, case, 'primary', review), 'Delivery joins')
            changed = copy.deepcopy(processing)
            changed['final_video_checks']['passed'] = False
            reject('broken_final_decode', lambda: audit_delivery.audit(
                attempt, changed, case, 'primary', review), 'Delivery joins')
            report_path = attempt / 'native-capture-report.json'
            report = json.loads(report_path.read_text())
            changed = copy.deepcopy(report)
            changed['restoration']['restored'] = False
            write_json(report_path, changed)
            reject('unrestored_world', lambda: audit_delivery.audit(
                attempt, processing, case, 'primary', review), 'ownership closure')
            write_json(report_path, report)
            with patch.object(audit_delivery, 'audit_motion',
                              return_value={'source_kind': 'original_native', 'status': 'not_met'}):
                reject('motion_not_met', lambda: audit_delivery.audit(
                    attempt, processing, case, 'primary', review), 'physical completion')
            review_value = json.loads(review.read_text())
            changed = copy.deepcopy(review_value)
            changed['views'].pop('overview')
            write_json(review, changed)
            reject('missing_camera_review', lambda: audit_delivery.audit(
                attempt, processing, case, 'primary', review), 'omits a source camera')
            changed = copy.deepcopy(review_value)
            changed['views']['overview']['rgb_sequence_sha256'] = '0' * 64
            write_json(review, changed)
            reject('changed_pixels', lambda: audit_delivery.audit(
                attempt, processing, case, 'primary', review), 'decoded pixel review changed')
            changed = copy.deepcopy(review_value)
            for view in changed['views'].values():
                view['subjects_visible'] = []
            write_json(review, changed)
            reject('scene_not_visible', lambda: audit_delivery.audit(
                attempt, processing, case, 'primary', review),
                   'pixels do not establish')
        return {'format': 'c146314-mocked-original-delivery-contract-v1',
                'case_id': case, 'mock_only': True, 'original_native_observed': False,
                'delivery_acceptance_claimed': False, 'legal_verdict_claimed': False,
                'contract_checks': list(audit_delivery.CHECKS),
                'negative_rejections': failures}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    assert args.case in {Path(__file__).resolve().parents[1].name + '__' + name
                         for name in ('reference', 'contrast')}
    proof = run(args.case)
    print(json.dumps(proof, sort_keys=True))
    if args.negative:
        print('EXPECTED CPU MOCK REJECTION: Original delivery sources changed')
        raise SystemExit(2)
