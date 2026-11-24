"""Exercise future original-source audit with labelled CPU mock inputs only."""
import argparse
import copy
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import audit_delivery

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def fixture(root, case):
    suffix = case.rsplit('__', 1)[-1]
    source = REPO / '.runtime-work' / f'c422978-selected-{suffix}-saved-attempt-v6'
    saved_source = REPO / '.runtime-work' / f'c422978-selected-{suffix}-saved-output-v6/v0001'
    attempt = root / 'mock-attempt'
    attempt.mkdir()
    for name in audit_delivery.SOURCES:
        target = attempt / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    actor_path = attempt / 'native-observed.jsonl'
    actor = rows(actor_path)
    for row in actor:
        row['source_kind'] = 'original_native'
    actor_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in actor))
    report_path = attempt / 'native-capture-report.json'
    report = json.loads(report_path.read_text())
    report['restoration'] = {'restored': True, 'cpu_mock': True}
    write(report_path, report)
    for name in ('city-survey-source.geojson', 'city-calibration.json',
                 'authority/synthetic-exception-source.json'):
        target = attempt / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / 'native/saved-fixtures' / suffix / 'primary' / name, target)
    hashes = {name: sha(attempt / name) for name in audit_delivery.SOURCES}
    saved = root / 'mock-saved/v0001'
    saved.mkdir(parents=True)
    result_path = saved / 'result.json'
    write(result_path, {'case_id': case, 'accepted': False,
                        'provenance_kind': 'native',
                        'cpu_mock_original_branch': True})
    review = {'case_id': case, 'source_kind': 'original_native_camera_pixels',
              'reviewer': 'CPU mock reviewer', 'method': 'source-bound CPU contract mock',
              'frame_map_sha256': hashes['video_frames.jsonl'],
              'legal_verdict_claimed': False, 'views': {}}
    for index, name in enumerate(audit_delivery.CAMERAS):
        decoded = json.loads((saved_source / f'source-{index}.json').read_text())
        write(saved.parent / f'source-{index}.json', decoded)
        review['views'][name] = {
            'video_sha256': hashes[name + '.mkv'],
            'reviewed_frame_ids': list(range(600)),
            'rgb_sequence_sha256': decoded['rgb_sequence_sha256'],
            'subjects_visible': ['heavy_vehicle_body', 'roadway', 'sidewalk_boundary']
            if index == 0 else []}
    pixel_path = root / 'mock-pixel-review.json'
    write(pixel_path, review)
    city_path = root / 'mock-city-review.json'
    write(city_path, {'reviewed': True, 'reviewer': 'CPU mock reviewer',
                      'citation': 'CPU mock; not a real City designation',
                      'city_sidewalk_authority': True, 'entrance_authority': True,
                      'map_readback_sha256': hashes['native-map-readback.json'],
                      'survey_source_sha256': sha(attempt / 'city-survey-source.geojson'),
                      'calibration_sha256': sha(attempt / 'city-calibration.json')})
    exception_path = root / 'mock-exception-review.json'
    document = 'authority/synthetic-exception-source.json'
    write(exception_path, {'reviewed': True, 'reviewer': 'CPU mock reviewer',
                           'citation': 'CPU mock; not a real subsection 2 finding',
                           'status': 'reviewed_not_applicable',
                           'native_capture_report_sha256': hashes['native-capture-report.json'],
                           'document_path': document,
                           'document_sha256': sha(attempt / document)})
    processing = {'case_id': case, 'candidate_id': 'primary', 'passed': True,
                  'recorded_only': True, 'originals_preserved': True,
                  'missing_evidence': False, 'original_source_hashes': hashes,
                  'timestamp_joins': {'passed': True, 'frames': 600},
                  'final_video_checks': {'passed': True, 'frames': 600},
                  'result': str(result_path), 'result_sha256': sha(result_path)}
    return attempt, processing, pixel_path, city_path, exception_path


def prove(case):
    scratch = REPO / '.runtime-work'
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c422978-delivery-contract-') as tmp:
        attempt, processing, pixel, city, exception = fixture(Path(tmp), case)
        def run(packet=processing):
            return audit_delivery.audit(attempt, packet, case, 'primary',
                                        pixel, city, exception)
        positive = run()
        assert positive['passed'] and positive['delivery_accepted']
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
        changed['original_source_hashes']['native-observed.jsonl'] = '0' * 64
        reject('changed_actor_source', lambda: run(changed), 'Original delivery sources changed')
        changed = copy.deepcopy(processing)
        changed['timestamp_joins']['passed'] = False
        reject('broken_time_join', lambda: run(changed), 'Delivery joins')
        review = json.loads(pixel.read_text())
        changed = copy.deepcopy(review)
        changed['views']['overview']['rgb_sequence_sha256'] = '0' * 64
        write(pixel, changed)
        reject('changed_pixels', run, 'decoded pixel review changed')
        write(pixel, review)
        city_value = json.loads(city.read_text())
        changed = copy.deepcopy(city_value)
        changed['reviewed'] = False
        write(city, changed)
        reject('unreviewed_city', run, 'City sidewalk and entrance authority')
        write(city, city_value)
        exception_value = json.loads(exception.read_text())
        changed = copy.deepcopy(exception_value)
        changed['status'] = 'pending'
        write(exception, changed)
        reject('unresolved_exception', run, 'Subsection 2 exception facts')
        write(exception, exception_value)
        return {'format': 'c422978-mocked-delivery-contract-v1',
                'case_id': case, 'mock_only': True, 'original_native_observed': False,
                'city_authority_reviewed': False, 'operator_exception_reviewed': False,
                'delivery_acceptance_claimed': False, 'legal_verdict': None,
                'contract_checks': list(audit_delivery.CHECKS),
                'negative_rejections': failures}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    assert args.case in {HERE.name + '__reference', HERE.name + '__contrast'}
    result = prove(args.case)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.negative:
        print('EXPECTED CPU MOCK REJECTION: Original delivery sources changed')
        raise SystemExit(2)
