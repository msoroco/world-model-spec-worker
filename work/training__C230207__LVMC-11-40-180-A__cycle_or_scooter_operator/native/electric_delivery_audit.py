"""Independent saved electric-device delivery audit for original Native evidence."""
import argparse
import json
from pathlib import Path

from delivery_audit import (VIEWS, SOURCES, check_sealed_sources, decode,
                            require, sha, source)
from electric_finalize import validate_electric_recording
from measure import measure


ASSIGNMENT = 'training__C230207__LVMC-11-40-180-A__cycle_or_scooter_operator'


def case_identity(case):
    for kind in ('electric_bicycle', 'electric_scooter'):
        for behavior in ('walk_cycle', 'mounted_sidewalk'):
            if case == f'{ASSIGNMENT}__{kind}_{behavior}':
                return kind, behavior
    raise ValueError('Wrong exact electric sidewalk delivery case')


def review_original(review, kind, behavior, binding, source_hashes, video_hashes):
    require(review.get('original_pixel_reviewed') is True and
            review.get('named_geography_verified') is True and
            review.get('sign_face_three_class_text_verified') is True and
            review.get('sidewalk_occupancy_reviewed') is True and
            review.get('operator_posture_reviewed') is True,
            'Original electric sidewalk, sign or posture review missing')
    require(review.get('electric_class_independently_verified') == kind and
            review.get('electric_power_source_reviewed') is True and
            review.get('electric_device_geometry_reviewed') is True and
            review.get('native_actor_id') == binding['native_actor_id'] and
            review.get('electric_asset_source_sha256') == binding['review_source_sha256'],
            'Original electric class, power, geometry or actor review missing')
    require(review.get('observed_behavior') == behavior,
            'Original electric operator behavior differs')
    require(review.get('source_sha256') == source_hashes and
            review.get('video_sha256') == video_hashes,
            'Original electric review source or pixels changed')


def audit(attempt, case):
    kind, behavior = case_identity(case)
    root = Path(attempt).resolve()
    binding = validate_electric_recording(root)
    require(binding['machine_class'] == kind, 'Exact electric case class differs')
    paths = {name: source(root, name) for name in SOURCES}
    context = json.loads(paths['restriction-context.json'].read_text())
    require(context.get('controlled_behavior') == behavior,
            'Original electric controlled behavior differs')
    observed = measure(paths['bicycle-poses.jsonl'], paths['restriction-context.json'],
                       paths['video_frames.jsonl'])
    require(observed['sidewalk_occupied_frames'] > 0,
            'Original electric sidewalk occupancy source absent')
    trace = [json.loads(line) for line in paths['trace.jsonl'].read_text().splitlines()]
    poses = [json.loads(line) for line in paths['bicycle-poses.jsonl'].read_text().splitlines()]
    require(len(trace) == len(poses) == 600 and all(
        trace[i].get('frame') == poses[i].get('native_frame') and
        abs(trace[i].get('time_s', -1) - poses[i]['time_s']) < 1e-6
        for i in range(600)), 'Original electric actor and trace join failed')
    videos = {name: decode(source(root, name + '.mkv'),
                           (1920, 1080) if name == 'overview' else (1280, 720))
              for name in VIEWS}
    source_hashes = {name: sha(path) for name, path in paths.items()}
    video_hashes = {name + '.mkv': videos[name]['sha256'] for name in VIEWS}
    review_path = source(root, 'fremont-original-review.json')
    review_original(json.loads(review_path.read_text()), kind, behavior, binding,
                    source_hashes, video_hashes)
    result = json.loads(source(root, 'result.json').read_text())
    require(result.get('case_id') == case and result.get('maneuver_completed') is True and
            result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met',
            'Original electric Native physical completion unverified')
    seal = json.loads(source(root, 'capture-seal.json').read_text())
    require(seal.get('provenance_kind') == 'native' and
            seal.get('diagnostic_fixture') is False,
            'Sealed original electric Native source missing')
    check_sealed_sources(seal, paths)
    return {'format': 'worker-c230207-electric-source-audit-v1',
            'case_id': case, 'passed': True, 'native_executed': True,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'electric_asset_binding': binding, 'source_sha256': source_hashes,
            'video_decode': videos, 'review_sha256': sha(review_path),
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case), sort_keys=True))
