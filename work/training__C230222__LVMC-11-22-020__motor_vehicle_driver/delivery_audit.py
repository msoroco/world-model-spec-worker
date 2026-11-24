"""Independent, source-bound C230222 delivery audit.

The CPU self-test checks the audit boundary. A passing delivery receipt requires
an original Native capture and a separate review of its actual camera pixels.
"""
import argparse
import hashlib
import json
from pathlib import Path


PREFIX = 'training__C230222__LVMC-11-22-020__motor_vehicle_driver__'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def joined_rows(attempt):
    names = ('native-ego-frames.jsonl', 'native-body-geometry.jsonl',
             'video_frames.jsonl', 'trace.jsonl')
    rows = [[json.loads(line) for line in (attempt / name).read_text().splitlines()]
            for name in names]
    require(all(len(stream) == 600 for stream in rows), 'Original 600-frame time join incomplete')
    for records in zip(*rows):
        frames = [r.get('native_frame') for r in records]
        times = [r.get('time_s') for r in records]
        require(len(set(frames)) == len(set(times)) == 1,
                'Original Native frame/time join differs')
    return rows


def pixel_review(attempt, path, case):
    review = read(path)
    require(review.get('format') == 'c230222-original-pixel-review-v1' and
            review.get('case_id') == case and review.get('reviewer') and
            review.get('method') and review.get('source_kind') == 'original_native_pixels' and
            review.get('legal_verdict_claimed') is False,
            'Independent original pixel review missing')
    views = review.get('views', {})
    require(set(views) == set(CAMERAS), 'Original pixel review omits a camera')
    for camera in CAMERAS:
        item = views[camera]
        require(item.get('video_sha256') == sha(attempt / (camera + '.mkv')) and
                item.get('reviewed_frames', 0) > 0 and
                item.get('vehicle_visible') is True and
                item.get('pedestrian_visibility_assessed') is True and
                item.get('curbside_context_assessed') is True,
                'Original camera pixels unreviewed: ' + camera)
    return review


def audit(case, attempt, saved, review_path, output):
    require(case in (PREFIX + 'probe_a', PREFIX + 'probe_b'), 'Select exact curbside case')
    attempt, saved = Path(attempt).resolve(), Path(saved).resolve()
    require(attempt.is_dir() and saved.is_dir(), 'Original attempt or saved processing absent')
    provenance = read(attempt / 'acquisition-provenance.json')
    seal = read(attempt / 'capture-seal.json')
    require(provenance.get('provenance_kind') == 'original_native' and
            provenance.get('diagnostic_fixture') is False and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and
            seal.get('frames') == 600 and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            seal.get('restoration', {}).get('restored') is True and
            all(seal.get('encoder_exit_codes', {}).get(name) == 0 for name in CAMERAS),
            'Original Native capture closure incomplete')
    for name, expected in seal.get('sources', {}).items():
        require(sha(attempt / name) == expected, 'Sealed Native source changed: ' + name)
    native_exit = read(attempt / 'native-exit.json')
    owner = read(attempt / 'owner-release.json')
    require(native_exit.get('capture_seal_sha256') == sha(attempt / 'capture-seal.json') and
            owner.get('native_exit_sha256') == sha(attempt / 'native-exit.json') and
            owner.get('event') == 'owner_released',
            'Saved processing precedes Native exit or owner release')
    processing = read(saved / 'processing.json')
    require(processing.get('case_id') == case and processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('timestamp_joins', {}).get('frames') == 600 and
            processing.get('missing_evidence') is False,
            'Saved-only processing lacks complete original joins')
    result_path = Path(processing['result']).resolve()
    result = read(result_path)
    require(result.get('case_id') == case and
            result.get('provenance_kind') == 'native' and
            result.get('diagnostic_fixture') is False and
            result.get('maneuver_completed') is True and
            result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met' and
            result.get('legal_acceptance_claimed') is False,
            'Original physical completion evidence missing')
    rows = joined_rows(attempt)
    context = read(attempt / 'driving-context.json')
    require(context.get('pedestrian_id') is not None and
            all(row.get('native_frame') is not None for row in rows[1]),
            'Original vehicle or pedestrian source missing')
    pixel_review(attempt, review_path, case)
    from worker_exchange.media import audit as decode
    mapping_hash = sha(attempt / 'video_frames.jsonl')
    decode_dir = Path(output).resolve().parent / (case + '-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    source_receipts = {}
    for camera in CAMERAS:
        path = attempt / (camera + '.mkv')
        receipt_path = decode_dir / (camera + '.json')
        source_receipts[camera] = decode(path, 600, receipt=receipt_path,
                                         mapping_sha256=mapping_hash)
    primary = source_receipts['overview']
    receipt_path = decode_dir / 'overview.json'
    receipt = {'format': 'worker-delivery-audit', 'passed': True,
               'case_id': case, 'frames': 600,
               'checks': {name: True for name in CHECKS},
               'attempt_path': str(attempt), 'saved_path': str(saved),
               'source_result_sha256': sha(result_path),
               'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
               'owner_receipt_path': str(attempt / 'owner-release.json'),
               'owner_receipt_sha256': sha(attempt / 'owner-release.json'),
               'video': 'overview.mkv', 'video_sha256': sha(attempt / 'overview.mkv'),
               'trace': 'trace.jsonl', 'trace_sha256': sha(attempt / 'trace.jsonl'),
               'source_decode_receipt_path': str(receipt_path),
               'source_decode_receipt_sha256': sha(receipt_path),
               'source_decode_auditor_sha256': primary['auditor_sha256'],
               'pixel_review_sha256': sha(review_path),
               'legal_verdict_claimed': False}
    Path(output).write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def selftest(case):
    require(case in (PREFIX + 'probe_a', PREFIX + 'probe_b'), 'Select exact curbside case')
    assert len(CAMERAS) == 4 and len(CHECKS) == 6
    try:
        require(False, 'test rejection')
    except ValueError as error:
        assert str(error) == 'test rejection'
    print('PASS exact curbside audit identity, camera inventory and rejection helper')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--saved')
    parser.add_argument('--pixel-review')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.case)
    else:
        audit(args.case, args.attempt, args.saved, args.pixel_review, args.output)
