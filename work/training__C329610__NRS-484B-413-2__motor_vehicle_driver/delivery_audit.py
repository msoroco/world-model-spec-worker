"""Independent C329610 original-source delivery audit and CPU boundary self-test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

PREFIX = 'training__C329610__NRS-484B-413-2__motor_vehicle_driver__'
SUFFIXES = ('below_100_ft', 'at_100_ft', 'above_100_ft',
            'below_300_ft', 'at_300_ft', 'above_300_ft')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(case, attempt, saved, pixel_review, output):
    require(case in tuple(PREFIX + suffix for suffix in SUFFIXES), 'Select exact signal case')
    attempt, saved = Path(attempt).resolve(), Path(saved).resolve()
    require(attempt.is_dir() and saved.is_dir(), 'Original attempt or saved processing absent')
    provenance = read(attempt / 'acquisition-provenance.json')
    seal = read(attempt / 'capture-seal.json')
    require(provenance.get('provenance_kind') == 'original_native' and
            provenance.get('diagnostic_fixture') is False and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and
            seal.get('frames') == 800 and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            seal.get('restoration', {}).get('restored') is True and
            all(seal.get('encoder_exit_codes', {}).get(camera) == 0 for camera in CAMERAS),
            'Original Native closure incomplete')
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
            processing.get('timestamp_joins', {}).get('frames') == 800 and
            processing.get('missing_evidence') is False,
            'Saved-only processing lacks complete original joins')
    result_path = Path(processing['result']).resolve()
    result = read(result_path)
    require(result.get('case_id') == case and result.get('provenance_kind') == 'native' and
            result.get('diagnostic_fixture') is False and
            result.get('maneuver_completed') is True and
            result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met' and
            result.get('legal_acceptance_claimed') is False,
            'Original physical completion evidence missing')
    native, trace, mapping = (rows(attempt / name) for name in
                              ('native_samples.jsonl', 'trace.jsonl', 'video_frames.jsonl'))
    require(len(native) == len(trace) == len(mapping) == 800, 'Original 800-frame join incomplete')
    for n, t, m in zip(native, trace, mapping):
        frame = m.get('carla_frame')
        require(frame == n.get('frame') == t.get('frame') and
                abs(m.get('time_s') - n.get('time_s')) < 1e-4 and
                abs(m.get('time_s') - t.get('time_s')) < 1e-4,
                'Original Native frame/time join differs')
    require(all(n.get('vehicle') or n.get('ego') or n.get('position_m') for n in native),
            'Original motor vehicle participant missing')
    review = read(pixel_review)
    require(review.get('case_id') == case and review.get('source_kind') == 'original_native_pixels' and
            review.get('reviewer') and review.get('method') and
            review.get('legal_verdict_claimed') is False and
            set(review.get('views', {})) == set(CAMERAS),
            'Independent original pixel review missing')
    for camera in CAMERAS:
        item = review['views'][camera]
        require(item.get('video_sha256') == sha(attempt / (camera + '.mkv')) and
                item.get('reviewed_frames', 0) > 0 and
                item.get('vehicle_visible') is True and
                item.get('signal_visibility_assessed') is True and
                item.get('area_context_assessed') is True,
                'Original camera pixels unreviewed: ' + camera)
    from worker_exchange.media import audit as decode
    decode_dir = Path(output).resolve().parent / (case + '-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for camera in CAMERAS:
        receipts[camera] = decode(attempt / (camera + '.mkv'), 800,
                                  receipt=decode_dir / (camera + '.json'),
                                  mapping_sha256=sha(attempt / 'video_frames.jsonl'))
    receipt = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': case,
               'frames': 800, 'checks': {check: True for check in CHECKS},
               'attempt_path': str(attempt), 'saved_path': str(saved),
               'source_result_sha256': sha(result_path),
               'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
               'owner_receipt_path': str(attempt / 'owner-release.json'),
               'owner_receipt_sha256': sha(attempt / 'owner-release.json'),
               'video': 'overview.mkv', 'video_sha256': sha(attempt / 'overview.mkv'),
               'trace': 'trace.jsonl', 'trace_sha256': sha(attempt / 'trace.jsonl'),
               'source_decode_receipt_path': str(decode_dir / 'overview.json'),
               'source_decode_receipt_sha256': sha(decode_dir / 'overview.json'),
               'source_decode_auditor_sha256': receipts['overview']['auditor_sha256'],
               'pixel_review_sha256': sha(pixel_review), 'legal_verdict_claimed': False}
    Path(output).write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def selftest(case, negative):
    require(case in tuple(PREFIX + suffix for suffix in SUFFIXES), 'Select exact signal case')
    require(len(CAMERAS) == 4 and len(CHECKS) == 6, 'Incomplete audit inventory')
    scratch_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    require('.runtime-work' in scratch_root.parts, 'Audit fixture scratch must remain under .runtime-work')
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as temporary:
        attempt = Path(temporary) / 'attempt'
        saved = Path(temporary) / 'saved'
        attempt.mkdir()
        saved.mkdir()
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}))
        (attempt / 'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'diagnostic_fixture': True}))
        try:
            audit(case, attempt, saved, 'unused', Path(temporary) / 'unused.json')
        except ValueError as error:
            require(str(error) == 'Synthetic fixture cannot establish original Native delivery',
                    'Synthetic source was rejected for another reason')
            if negative:
                raise
        else:
            raise AssertionError('Synthetic source passed original Native delivery')
    print('PASS exact signal case, four cameras, six independent checks and synthetic rejection boundary')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-fixture', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--saved')
    parser.add_argument('--pixel-review')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.case, args.negative_fixture)
    else:
        audit(args.case, args.attempt, args.saved, args.pixel_review, args.output)
