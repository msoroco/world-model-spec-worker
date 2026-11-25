"""Verify both recorded-only municipal parking fixture runs and source bindings.

The saved attempts are local synthetic diagnostics. This proof never promotes
their source assertions into actual City records or physical acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = 'training__C150129__LVMC-11-52-340__motor_vehicle_driver'
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
REQUIRED = ('parking-inventory.json', 'review.json', 'vehicle-poses.jsonl',
            'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
            'source_context/city_street.txt',
            'source_context/council_designation.txt',
            'source_context/posting_or_marking.txt',
            'source_context/subject_vehicle_status.txt', *CAMERAS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify(case_number, attempt, processing):
    attempt = Path(attempt)
    report = processing if isinstance(processing, dict) else json.loads(Path(processing).read_text())
    case = ASSIGNMENT + '__controlled_' + str(case_number)
    require(report.get('format') == 'worker-saved-processing' and
            report.get('case_id') == case and report.get('candidate_id') == 'primary',
            'Saved exact case or candidate differs')
    for key in ('passed', 'recorded_only', 'originals_preserved'):
        require(report.get(key) is True, 'Saved processing proof missing: ' + key)
    require(report.get('timestamp_joins', {}).get('frames') == 600 and
            report['timestamp_joins'].get('passed') is True,
            'Original 600-frame join missing')
    require(report.get('physical_acceptance_claimed') is False and
            report.get('legal_acceptance_claimed') is False and
            report.get('missing_evidence') is False,
            'Saved acceptance boundary differs')
    source_hashes = report.get('original_source_hashes', {})
    for name in REQUIRED:
        path = attempt / name
        require(path.is_file() and source_hashes.get(name) == sha(path),
                'Original source missing or changed: ' + name)
    require(report.get('final_video_checks', {}).get('passed') is True and
            report['final_video_checks'].get('frames') == 600,
            'Full composed video decode missing')
    require(sha(attempt / 'construction.json') ==
            report.get('native_revision', {}).get('construction_sha256'),
            'Native construction changed after saved processing')
    rows = [json.loads(line) for line in
            (attempt / 'vehicle-poses.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in
              (attempt / 'video_frames.jsonl').read_text().splitlines()]
    require(len(rows) == len(frames) == 600 and all(
        row['video_frame'] == frame['video_frame'] == index and
        row['native_frame'] == frame['native_frame']
        for index, (row, frame) in enumerate(zip(rows, frames))),
        'Original vehicle and four-camera frame identity differs')
    result_path = Path(report['result'])
    require(result_path.is_file() and sha(result_path) == report.get('result_sha256'),
            'Saved result hash differs')
    result = json.loads(result_path.read_text())
    require(result.get('case_id') == case and result.get('accepted') is False,
            'Saved result asserts physical acceptance')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', default='.runtime-work')
    args = parser.parse_args()
    scratch = Path(args.scratch)
    proofs = []
    for number in (1, 2):
        attempt = scratch / ('c150129-saved-attempt-v3-' + str(number))
        processing = Path(__file__).resolve().parent / 'proofs' / (
            'saved-controlled_' + str(number) + '.json')
        report = verify(number, attempt, processing)
        proofs.append({'case_id': report['case_id'],
                       'processing_sha256': sha(processing),
                       'source_count': len(report['original_source_hashes']),
                       'frame_count': report['timestamp_joins']['frames'],
                       'composed_video_sha256': report['final_video_checks']['video_sha256']})
    corrupt = json.loads((Path(__file__).resolve().parent / 'proofs' /
                          'saved-controlled_2.json').read_text())
    corrupt['original_source_hashes']['source_context/posting_or_marking.txt'] = '0' * 64
    try:
        verify(2, scratch / 'c150129-saved-attempt-v3-2', corrupt)
    except ValueError as error:
        require(str(error) == 'Original source missing or changed: source_context/posting_or_marking.txt',
                'Wrong stale-source rejection')
    else:
        raise ValueError('Stale source hash was accepted')
    print(json.dumps({'passed': True, 'proofs': proofs,
                      'negative': 'stale posting source hash rejected',
                      'physical_or_legal_acceptance': False}, sort_keys=True))


if __name__ == '__main__':
    main()
