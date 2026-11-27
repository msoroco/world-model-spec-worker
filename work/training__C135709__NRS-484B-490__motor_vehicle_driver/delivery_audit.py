"""Independent original-source narrow-highway parking delivery audit.

CPU selftests inventory the checks and reject a synthetic fixture. Original
acceptance needs sealed Native sources, cited device authority/extent, full
camera decodes and reviewed sign pixels before this script can pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

PREFIX = 'training__C135709__NRS-484B-490__motor_vehicle_driver__'
CASES = {PREFIX + x for x in ('probe_01', 'probe_02')}
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(row) for row in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_sources(case, attempt):
    config = read(attempt / 'config.json')
    native = read(attempt / 'road-context.json')
    review = read(attempt / 'road-review.json')
    pixel = read(attempt / 'device-pixel-review.json')
    require(config.get('case_id') == case and native.get('case_id') == case and
            review.get('case_id') == case and pixel.get('case_id') == case,
            'Exact original parking case identity differs')
    require(review.get('synthetic_diagnostic') is False and
            pixel.get('source_kind') == 'independent_original_review',
            'Original narrow-road and device pixel reviews missing')
    require(review.get('native_context_sha256') == sha(attempt / 'road-context.json') and
            native.get('map_sha256') == sha(attempt / 'road.xodr'),
            'Independent road review changed Native readback')
    sources = review.get('sources', {})
    expected = {'highway', 'narrow_designation', 'official_authority',
                'device_erection', 'device_content', 'governed_extent'}
    require(set(sources) == expected, 'Original road/device source inventory incomplete')
    for name in expected:
        ref = sources[name]
        require(ref.get('path') == 'source_context/' + name + '.txt' and
                ref.get('sha256') == sha(attempt / ref['path']),
                'Original cited road/device source changed: ' + name)
    require(all(review.get(name) is True for name in
                ('roadway_is_highway', 'narrow_highway_designated',
                 'device_is_official', 'device_erected', 'device_prohibits_parking')) and
            review.get('device_id') == '490' and review.get('governed_road_id') == '1',
            'Original narrow-highway prohibitory-device activation unverified')
    extent = review.get('governed_extent_xyxy_m')
    require(isinstance(extent, list) and len(extent) == 4 and
            extent[0] < extent[2] and extent[1] < extent[3],
            'Original governed extent missing')
    require(pixel.get('road_review_sha256') == sha(attempt / 'road-review.json') and
            pixel.get('pose_sha256') == sha(attempt / 'vehicle-pose.jsonl') and
            pixel.get('frame_map_sha256') == sha(attempt / 'video_frames.jsonl'),
            'Independent pixel review changed road or frame source')
    for view in VIEWS:
        require(pixel.get('camera_sha256', {}).get(view) == sha(attempt / (view + '.mkv')),
                'Original pixel-review camera hash differs: ' + view)
    poses, trace, mapping = (rows(attempt / name) for name in
                             ('vehicle-pose.jsonl', 'trace.jsonl', 'video_frames.jsonl'))
    observations = pixel.get('device_observations', [])
    require(len(poses) == len(trace) == len(mapping) == len(observations) == 600,
            'Complete original 600-frame source and pixel join required')
    vehicle = poses[0].get('vehicle_id')
    require(vehicle is not None, 'Original parked vehicle identity missing')
    x0, y0, x1, y1 = extent
    occupied = []
    for i, (pose, actor, frame, observed) in enumerate(zip(poses, trace, mapping, observations)):
        require(pose.get('video_frame') == frame.get('video_frame') == observed.get('video_frame') == i and
                pose.get('native_frame') == frame.get('native_frame') == actor.get('frame') and
                pose.get('vehicle_id') == vehicle and
                abs(pose['time_s'] - frame['time_s']) < 1e-5 and
                abs(actor['time_s'] - frame['time_s']) < 1e-5 and
                pose.get('speed_mps') is not None and pose['speed_mps'] <= .1 and
                set(pose.get('camera_native_frames', {})) == set(VIEWS) and
                all(pose['camera_native_frames'][v] == frame['native_frame'] for v in VIEWS),
                'Original parked participant/frame/time join differs')
        require(observed.get('source_camera') in VIEWS and
                observed.get('pixel_box_xyxy') and
                observed.get('no_parking_device_visible') is True,
                'Original prohibitory device pixel review incomplete')
        half_x, half_y = pose['bbox_half_length_m'], pose['bbox_half_width_m']
        occupied.append(x0 <= pose['x_m'] - half_x and pose['x_m'] + half_x <= x1 and
                        y0 <= pose['y_m'] - half_y and pose['y_m'] + half_y <= y1)
    require(all(occupied) if case.endswith('probe_02') else not any(occupied),
            'Selected parked footprint is not in its planned governed-extent branch')
    return {'stationary_frames': 600, 'fully_inside_frames': sum(occupied),
            'device_pixel_frames': len(observations),
            'legal_verdict_claimed': False}


def audit(case, attempt, saved, output):
    require(case in CASES, 'Select exact narrow-highway parking case')
    attempt, saved, output = Path(attempt).resolve(), Path(saved).resolve(), Path(output).resolve()
    provenance, seal = read(attempt / 'acquisition-provenance.json'), read(attempt / 'capture-seal.json')
    require(provenance.get('provenance_kind') == 'original_native' and
            provenance.get('diagnostic_fixture') is False and
            seal.get('provenance_kind') == 'native' and
            seal.get('diagnostic_fixture') is False,
            'Synthetic fixture cannot establish original Native delivery')
    require(seal.get('format') == 'worker-sealed-capture' and seal.get('frames') == 600 and
            seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'] and
            seal.get('restoration', {}).get('restored') is True and
            all(seal.get('encoder_exit_codes', {}).get(view) == 0 for view in VIEWS),
            'Original Native capture closure incomplete')
    for name, checksum in seal.get('sources', {}).items():
        require(sha(attempt / name) == checksum, 'Sealed original source changed: ' + name)
    exit_record, owner = read(attempt / 'native-exit.json'), read(attempt / 'owner-release.json')
    require(exit_record.get('capture_seal_sha256') == sha(attempt / 'capture-seal.json') and
            owner.get('native_exit_sha256') == sha(attempt / 'native-exit.json') and
            owner.get('event') == 'owner_released',
            'Saved processing precedes Native exit or owner release')
    processing = read(saved / 'processing.json')
    require(processing.get('case_id') == case and processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('missing_evidence') is False and
            processing.get('timestamp_joins', {}).get('frames') == 600,
            'Saved-only original processing incomplete')
    result = read(Path(processing['result']).resolve())
    require(result.get('case_id') == case and result.get('provenance_kind') == 'native' and
            result.get('diagnostic_fixture') is not True,
            'Saved original result provenance differs')
    physical = inspect_sources(case, attempt)
    from worker_exchange.media import audit as decode
    decode_dir = output.parent / (case + '-source-decode')
    decode_dir.mkdir(parents=True, exist_ok=True)
    receipts = {view: decode(attempt / (view + '.mkv'), 600,
                             receipt=decode_dir / (view + '.json'),
                             mapping_sha256=sha(attempt / 'video_frames.jsonl'))
                for view in VIEWS}
    core = Path(processing['version']) / 'converted/trace.json'
    require(core.is_file() and len(read(core).get('scenes', [])) == 600,
            'Saved original Core scene sequence unavailable')
    receipt = {'format': 'worker-delivery-audit', 'passed': True,
               'case_id': case, 'frames': 600,
               'checks': {name: True for name in CHECKS},
               'source_result_sha256': processing['result_sha256'],
               'video': 'overview.mkv', 'video_sha256': sha(attempt / 'overview.mkv'),
               'trace': str(core), 'trace_sha256': sha(core),
               'source_decode_receipt_path': str(decode_dir / 'overview.json'),
               'source_decode_receipt_sha256': sha(decode_dir / 'overview.json'),
               'source_decode_auditor_sha256': receipts['overview']['auditor_sha256'],
               'auditor_path': str(Path(__file__).resolve()),
               'auditor_sha256': sha(__file__),
               'physical_observables': physical, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def selftest(case, negative):
    require(case in CASES and len(VIEWS) == 4 and len(CHECKS) == 6,
            'Exact case or independent audit inventory differs')
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    require('.runtime-work' in scratch.parts, 'Diagnostic scratch outside .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        attempt, saved = Path(temp) / 'attempt', Path(temp) / 'saved'
        attempt.mkdir(); saved.mkdir()
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}) + '\n')
        (attempt / 'capture-seal.json').write_text(json.dumps({
            'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True}) + '\n')
        try:
            audit(case, attempt, saved, Path(temp) / 'audit.json')
        except ValueError as error:
            require(str(error) == 'Synthetic fixture cannot establish original Native delivery',
                    'Synthetic fixture rejected for wrong reason')
            if negative:
                raise
        else:
            raise AssertionError('Synthetic fixture passed original delivery')
    print('PASS six original-source checks inventoried; synthetic delivery rejected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-fixture', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--saved')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.case, args.negative_fixture)
    else:
        print(json.dumps(audit(args.case, args.attempt, args.saved, args.output), sort_keys=True))
