"""Independent source-bound delivery audit for NRS 484B.270(7)(a).

The diagnostic command checks software wiring and cannot accept original motion.
Only an independently reviewed Native attempt can produce a delivery receipt.
"""

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = 'testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(),
            'delivery source missing or linked: ' + str(path))
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved(attempt, processing_path, case_id):
    attempt = Path(attempt).resolve()
    require(case_id.startswith(ASSIGNMENT + '__'), 'exact assignment case required')
    receipt = read(processing_path)
    require(receipt.get('format') == 'worker-saved-processing' and
            receipt.get('passed') is True and
            receipt.get('recorded_only') is True and
            receipt.get('originals_preserved') is True and
            receipt.get('missing_evidence') is False and
            receipt.get('case_id') == case_id and
            receipt.get('timestamp_joins', {}).get('frames') == 600 and
            receipt.get('timestamp_joins', {}).get('passed') is True and
            receipt.get('final_video_checks', {}).get('frames') == 600,
            'complete exact recorded-only processing receipt required')
    for relative, checksum in receipt.get('original_source_hashes', {}).items():
        source = (attempt / relative).resolve()
        require(source.is_relative_to(attempt) and source.is_file() and
                not source.is_symlink() and sha(source) == checksum,
                'saved original changed: ' + relative)
    result_path = Path(receipt['result']).resolve()
    require(result_path.is_file() and sha(result_path) ==
            receipt.get('result_sha256'), 'saved result changed')
    result = read(result_path)
    require(result.get('case_id') == case_id,
            'saved result belongs to another case')
    return receipt, result


def diagnostic(attempt, processing_path, case_id):
    receipt, result = saved(attempt, processing_path, case_id)
    provenance = read(Path(attempt) / 'acquisition-provenance.json')
    require(provenance.get('provenance_kind') == 'synthetic_fixture' and
            provenance.get('diagnostic_fixture') is True and
            result.get('diagnostic_fixture') is True and
            receipt.get('final_video_checks', {}).get('passed') is True,
            'synthetic saved-only diagnostic proof incomplete')
    return {'format': 'c147344-delivery-audit-diagnostic-v1',
            'case_id': case_id, 'recorded_only': True,
            'originals_preserved': True, 'joined_frames': 600,
            'full_final_decode': True, 'diagnostic_fixture': True,
            'native_source': False, 'actual_pixels': False,
            'physical_completion': False, 'legal_judgment': None}


def original(attempt, processing_path, case_id, review_path,
             pixel_review_path, video_relative, trace_relative,
             decode_receipt, auditor_path, job_id, attempt_number,
             recording_id):
    attempt = Path(attempt).resolve()
    receipt, result = saved(attempt, processing_path, case_id)
    provenance = read(attempt / 'acquisition-provenance.json')
    require(provenance.get('provenance_kind') == 'native' and
            provenance.get('diagnostic_fixture') is False and
            result.get('diagnostic_fixture') is False,
            'original Native bicycle and motor vehicle attempt required')
    seal = read(attempt / 'capture-seal.json')
    require(seal.get('events') ==
            ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            read(attempt / 'native-exit.json').get('event') == 'native_exit' and
            read(attempt / 'owner-release.json').get('operator_attested') is True,
            'Native exit, restoration and owner release required')
    review = read(review_path)
    source_hashes = review.get('source_hashes', {})
    required = ('scene-context.json', 'original-sources.json',
                'interaction-readback.jsonl', 'trace.jsonl',
                'video_frames.jsonl') + tuple(name + '.mkv' for name in VIEWS)
    for name in required:
        require(source_hashes.get(name) == sha(attempt / name),
                'independent original source review absent or stale: ' + name)
    observation = result.get('measured_values', {})
    require(observation.get('frame_count') == 600 and
            observation.get('bicycle_id') and
            observation.get('motor_vehicle_id') and
            observation['bicycle_id'] != observation['motor_vehicle_id'] and
            observation.get('motor_vehicle_moved') is True and
            observation.get('intent_inferred_from_motion') is False and
            result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met' and
            result.get('maneuver_completed') is True,
            'physical completion or required participants lack original evidence')
    pixel = read(pixel_review_path)
    require(pixel.get('case_id') == case_id and
            pixel.get('reviewer') and pixel.get('method') and
            set(pixel.get('views', {})) == set(VIEWS),
            'independent original pixel review missing')
    for name in VIEWS:
        item = pixel['views'][name]
        require(item.get('video_sha256') == sha(attempt / (name + '.mkv')) and
                item.get('electric_bicycle_visible') is True and
                item.get('motor_vehicle_visible') is True and
                item.get('reviewed_frames') and
                item.get('visibility_method'),
                'original pixels or participant missing: ' + name)
    video = (attempt / video_relative).resolve()
    trace = (attempt / trace_relative).resolve()
    require(video.is_relative_to(attempt) and trace.is_relative_to(attempt) and
            video.is_file() and trace.is_file(),
            'canonical video or Core trace escapes original attempt')
    from worker_exchange.media import audit as decode
    decoded = decode(video, 600,
                     mapping_sha256=sha(attempt / 'video_frames.jsonl'),
                     receipt=decode_receipt)
    require(decoded.get('passed') is True and decoded.get('frames') == 600,
            'full original video decode incomplete')
    require(Path(auditor_path).resolve() == Path(__file__).resolve(),
            'auditor source path differs')
    return {'format': 'worker-delivery-audit', 'passed': True,
            'case_id': case_id, 'job_id': job_id,
            'attempt': attempt_number, 'recording_id': recording_id,
            'checks': {name: True for name in CHECKS},
            'source_result_sha256': sha(attempt / 'result.json'),
            'video': video_relative, 'video_sha256': sha(video),
            'trace': trace_relative, 'trace_sha256': sha(trace),
            'frames': 600, 'auditor_path': str(Path(auditor_path).resolve()),
            'auditor_sha256': sha(auditor_path),
            'source_decode_receipt_path': str(Path(decode_receipt).resolve()),
            'source_decode_receipt_sha256': sha(decode_receipt),
            'source_decode_auditor_sha256': decoded['auditor_sha256'],
            'originals_preserved': receipt['originals_preserved'],
            'pixel_review_sha256': sha(pixel_review_path),
            'physical_acceptance_claimed': False,
            'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--pixel-review', type=Path)
    parser.add_argument('--video')
    parser.add_argument('--trace')
    parser.add_argument('--decode-receipt', type=Path)
    parser.add_argument('--auditor', type=Path)
    parser.add_argument('--job')
    parser.add_argument('--attempt-number', type=int)
    parser.add_argument('--recording-id')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.diagnostic:
        value = diagnostic(args.attempt, args.processing, args.case)
    else:
        required = (args.review, args.pixel_review, args.video, args.trace,
                    args.decode_receipt, args.auditor, args.job,
                    args.attempt_number, args.recording_id)
        require(all(item is not None for item in required),
                'independent original delivery audit inputs required')
        value = original(args.attempt, args.processing, args.case,
                         args.review, args.pixel_review, args.video,
                         args.trace, args.decode_receipt, args.auditor,
                         args.job, args.attempt_number, args.recording_id)
    if args.output:
        require(not args.output.exists(), 'retain prior delivery audit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    main()
