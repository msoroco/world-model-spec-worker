"""Independent original-source delivery audit for the C329610 speed turn."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

AID = 'training__C329610__NRS-484B-600-1e__motor_vehicle_driver'
CASES = tuple(AID+'__'+s for s in ('probe_a', 'probe_at', 'probe_b'))
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


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
    require(case in CASES, 'Select exact C329610 speed case')
    attempt, saved, output = Path(attempt).resolve(), Path(saved).resolve(), Path(output).resolve()
    require(attempt.is_dir() and saved.is_dir(), 'Original attempt or saved processing absent')
    provenance, seal = read(attempt/'acquisition-provenance.json'), read(attempt/'capture-seal.json')
    require(provenance.get('provenance_kind') == 'native' and
            provenance.get('diagnostic_fixture') is False and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and seal.get('frames') == 600 and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            seal.get('restoration', {}).get('restored') is True and
            all(seal.get('encoder_exit_codes', {}).get(name) == 0 for name in CAMERAS),
            'Original Native capture closure incomplete')
    for name, digest in seal.get('sources', {}).items():
        require(sha(attempt/name) == digest, 'Sealed Native source changed: '+name)
    native_exit, owner = read(attempt/'native-exit.json'), read(attempt/'owner-release.json')
    require(native_exit.get('capture_seal_sha256') == sha(attempt/'capture-seal.json') and
            owner.get('native_exit_sha256') == sha(attempt/'native-exit.json') and
            owner.get('event') == 'owner_released',
            'Saved processing precedes Native exit or owner release')
    processing = read(saved/'processing.json')
    require(processing.get('case_id') == case and processing.get('passed') is True and
            processing.get('recorded_only') is True and processing.get('originals_preserved') is True and
            processing.get('timestamp_joins', {}).get('frames') == 600 and
            processing.get('missing_evidence') is False,
            'Saved processing lacks complete original joins')
    result_path = Path(processing['result']).resolve()
    result = read(result_path)
    require(result.get('case_id') == case and result.get('provenance_kind') == 'native' and
            result.get('diagnostic_fixture') is not True and
            result.get('legal_verdict_claimed') is False,
            'Original saved analysis or provenance missing')
    motion, trace, mapping = (rows(attempt/name) for name in
                              ('native_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl'))
    require(len(motion) == len(trace) == len(mapping) == 600,
            'Original 600-frame motion/trace/map join incomplete')
    route = []
    for index, (sample, telemetry, frame_map) in enumerate(zip(motion, trace, mapping)):
        frame = frame_map.get('carla_frame')
        require(frame == sample.get('native_frame') == telemetry.get('frame') and
                frame_map.get('video_frame') == sample.get('video_frame') == index and
                abs(frame_map.get('time_s')-sample.get('time_s')) < 1e-4 and
                abs(frame_map.get('time_s')-telemetry.get('time_s')) < 1e-4,
                'Original Native frame/time join differs')
        require(sample.get('source_kind') == 'original_native_velocity' and
                sample.get('ego_actor_id') == read(attempt/'road_context.json').get('ego_actor_id') and
                sample.get('lane_id') == -1 and sample.get('road_id') in (1, 13, 4),
                'Original vehicle identity or signed left-turn lane missing')
        route.append(sample['road_id'])
    require(list(dict.fromkeys(route)) == [1, 13, 4],
            'Original source did not complete the left turn')
    from speed_measure import measure
    observed = measure(attempt)
    require(observed['review_kind'] == 'original_source_review' and
            observed['sample_count'] == 600 and observed['statutory_cap_mph'] == 80 and
            observed['legal_verdict_claimed'] is False,
            'Original source-bound speed measurement missing')
    require(result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met' and
            result.get('maneuver_completed') is True,
            'Original physical completion unverified')
    review = read(pixel_review)
    require(review.get('case_id') == case and review.get('source_kind') == 'original_native_pixels' and
            review.get('reviewer') and review.get('method') and
            review.get('legal_verdict_claimed') is False and
            set(review.get('views', {})) == set(CAMERAS),
            'Independent original pixel review missing')
    for camera in CAMERAS:
        item = review['views'][camera]
        require(item.get('video_sha256') == sha(attempt/(camera+'.mkv')) and
                item.get('reviewed_frames', 0) > 0 and item.get('ego_visible') is True,
                'Original camera pixels unreviewed: '+camera)
    from worker_exchange.media import audit as decode
    decode_dir = output.parent/(case+'-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {name: decode(attempt/(name+'.mkv'), 600,
                             mapping_sha256=sha(attempt/'video_frames.jsonl'),
                             receipt=decode_dir/(name+'.json')) for name in CAMERAS}
    report = {'format': 'worker-delivery-audit', 'passed': True, 'case_id': case,
              'frames': 600, 'checks': {name: True for name in CHECKS},
              'attempt_path': str(attempt), 'saved_path': str(saved),
              'source_result_sha256': sha(result_path),
              'capture_seal_sha256': sha(attempt/'capture-seal.json'),
              'owner_receipt_path': str(attempt/'owner-release.json'),
              'owner_receipt_sha256': sha(attempt/'owner-release.json'),
              'video': 'overview.mkv', 'video_sha256': sha(attempt/'overview.mkv'),
              'trace': 'trace.jsonl', 'trace_sha256': sha(attempt/'trace.jsonl'),
              'source_decode_receipt_path': str(decode_dir/'overview.json'),
              'source_decode_receipt_sha256': sha(decode_dir/'overview.json'),
              'source_decode_auditor_sha256': receipts['overview']['auditor_sha256'],
              'pixel_review_sha256': sha(pixel_review),
              'maximum_original_speed_mph': observed['maximum_observed_mph_while_driving'],
              'frames_above_80_mph': observed['frames_above_80_mph'],
              'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2)+'\n')
    return report


def selftest(case, negative):
    require(case in CASES and len(CHECKS) == 6 and len(CAMERAS) == 4,
            'Audit inventory or exact case differs')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts, 'Audit scratch must be under .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        attempt, saved = Path(temporary)/'attempt', Path(temporary)/'saved'
        attempt.mkdir(); saved.mkdir()
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})+'\n')
        (attempt/'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'diagnostic_fixture': True})+'\n')
        try:
            audit(case, attempt, saved, 'unused', Path(temporary)/'unused.json')
        except ValueError as error:
            require(str(error) == 'Synthetic fixture cannot establish original Native delivery',
                    'Synthetic rejection occurred for another reason')
            if negative:
                raise
        else:
            raise AssertionError('Synthetic fixture passed original Native delivery')
    print('PASS exact C329610 speed case, six-check inventory and synthetic rejection')


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
    selftest(args.case, args.negative_fixture) if args.selftest else audit(
        args.case, args.attempt, args.saved, args.pixel_review, args.output)
