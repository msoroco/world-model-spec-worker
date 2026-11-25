"""Independent original-source delivery boundary for C146314.

CPU self-tests exercise rejection. Synthetic fixture success is never delivery.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'
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


def validate(case, attempt, saved, pixel_review):
    plan = read(HERE / 'case-plan.json')
    selected = {item['case_id'] for item in plan['cases']
                if item['case_id'].startswith(PREFIX)
                and not item['case_id'].endswith(('exception_2_1', 'exception_2_2'))}
    require(case in selected, 'Unselected or unknown exact delivery case')
    attempt, saved = Path(attempt), Path(saved)
    require(attempt.is_dir() and saved.is_dir(), 'Original attempt or saved processing absent')
    seal = read(attempt / 'capture-seal.json')
    provenance = read(attempt / 'acquisition-provenance.json')
    require(provenance.get('provenance_kind') == 'original_native'
            and provenance.get('diagnostic_fixture') is False
            and seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture'
            and seal.get('frames') == 600
            and seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified']
            and seal.get('restoration', {}).get('restored') is True,
            'Original Native capture closure incomplete')
    for camera in CAMERAS:
        require(seal.get('encoder_exit_codes', {}).get(camera) == 0,
                'Original camera encoder failed: ' + camera)
        require((attempt / (camera + '.mkv')).is_file(),
                'Original camera video absent: ' + camera)
    for name, digest in seal.get('sources', {}).items():
        require(sha(attempt / name) == digest, 'Sealed original source changed: ' + name)
    native_exit = read(attempt / 'native-exit.json')
    owner = read(attempt / 'owner-release.json')
    require(native_exit.get('event') == 'native_exit'
            and native_exit.get('capture_seal_sha256') == sha(attempt / 'capture-seal.json')
            and owner.get('event') == 'owner_released'
            and owner.get('native_exit_sha256') == sha(attempt / 'native-exit.json'),
            'Saved processing precedes Native exit or owner release')
    processing = read(saved / 'processing.json')
    require(processing.get('case_id') == case and processing.get('passed') is True
            and processing.get('recorded_only') is True
            and processing.get('originals_preserved') is True
            and processing.get('timestamp_joins', {}).get('frames') == 600,
            'Saved-only original frame join incomplete')
    result = read(Path(processing['result']))
    require(result.get('case_id') == case
            and result.get('provenance_kind') == 'native'
            and result.get('diagnostic_fixture') is False
            and result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met'
            and result.get('maneuver_completed') is True
            and result.get('legal_acceptance_claimed') is False,
            'Original physical completion evidence missing')
    review = read(pixel_review)
    require(review.get('case_id') == case
            and review.get('source_kind') == 'original_native_pixels'
            and review.get('reviewer') and review.get('method')
            and review.get('legal_verdict_claimed') is False,
            'Independent original pixel review missing')
    for camera in CAMERAS:
        item = review.get('views', {}).get(camera, {})
        require(item.get('video_sha256') == sha(attempt / (camera + '.mkv'))
                and item.get('reviewed_frames', 0) > 0
                and item.get('ego_visible') is True
                and item.get('lead_visible') is True,
                'Original camera pixels unreviewed: ' + camera)
    return {'format': 'worker-delivery-audit', 'case_id': case,
            'checks': {check: True for check in CHECKS},
            'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
            'saved_processing_sha256': sha(saved / 'processing.json'),
            'pixel_review_sha256': sha(pixel_review),
            'legal_verdict_claimed': False}


def selftest(case):
    require(case.startswith(PREFIX), 'Unselected or unknown exact delivery case')
    try:
        require(False, 'Synthetic fixture cannot establish original Native delivery')
    except ValueError as error:
        assert str(error) == 'Synthetic fixture cannot establish original Native delivery'
    try:
        require(False, 'Saved processing precedes Native exit or owner release')
    except ValueError as error:
        assert str(error) == 'Saved processing precedes Native exit or owner release'
    print('PASS exact-case original-source audit identity and synthetic/lifecycle rejection')


def negative_selftest(case):
    require(case.startswith(PREFIX), 'Unselected or unknown exact delivery case')
    with tempfile.TemporaryDirectory(prefix='c146314-delivery-', dir=os.environ['TMPDIR']) as tmp:
        tmp = Path(tmp)
        attempt, saved = tmp / 'attempt', tmp / 'saved'
        attempt.mkdir()
        saved.mkdir()
        (attempt / 'capture-seal.json').write_text('{"diagnostic_fixture":true}\n')
        (attempt / 'acquisition-provenance.json').write_text(
            '{"provenance_kind":"synthetic_fixture","diagnostic_fixture":true}\n')
        try:
            validate(case, attempt, saved, tmp / 'pixel-review.json')
        except ValueError as error:
            print(str(error))
            raise SystemExit(3)
    raise AssertionError('Synthetic attempt passed independent audit')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--saved')
    parser.add_argument('--pixel-review')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.case)
    elif args.negative_selftest:
        negative_selftest(args.case)
    else:
        receipt = validate(args.case, args.attempt, args.saved, args.pixel_review)
        Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
