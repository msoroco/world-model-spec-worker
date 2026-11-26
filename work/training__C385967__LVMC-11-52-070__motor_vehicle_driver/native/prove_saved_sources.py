"""Synthetic CPU source-join and parking-pose diagnostics for both angle branches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

from physical_preparation import assess
from saved_measure import process

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c385967-source-proof'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(case, yaw, *, moving=False):
    folder = SCRATCH / (case.rsplit('__', 1)[-1] + ('-moving' if moving else ''))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'permission-source.bin').write_text(
        'SYNTHETIC CPU FIXTURE. No City Traffic Engineer permission is asserted.\n')
    write(folder / 'permission_authority.json', {
        'source_kind': 'synthetic_cpu_fixture', 'authority_claim': 'City Traffic Engineer',
        'source_file': 'permission-source.bin',
        'source_sha256': sha(folder / 'permission-source.bin'),
        'permission_verified': False, 'authored_sign_not_permission_evidence': True,
        'independent_authority_and_street_review_required': True})
    write(folder / 'road_geometry.json', {
        'provenance': 'synthetic_cpu_fixture', 'native_map_sha256': 'a'*64,
        'native_road_id': 1, 'driving_lane_id': -1, 'parking_lane_id': -2,
        'lawful_traffic_heading_deg': 90, 'bay_center_xy_m': [6.5, 0],
        'bay_heading_deg': 45, 'bay_extent_length_m': 6,
        'bay_extent_width_m': 3, 'sign_or_marking_readback_review_required': True})
    write(folder / 'parking_context.json', {
        'control': 'angle_parking_designation', 'native_actor_id': 17,
        'native_road_id': 1, 'native_parking_lane_id': -2,
        'requested_activity': 'standing_or_parked',
        'actual_activity_and_bay_containment_review_required': True})
    samples, mapping, bodies = [], [], []
    for index in range(600):
        frame = 1000 + index
        time_s = (index + 1)/20
        samples.append({'case_id': case, 'frame': index, 'sample_index': index,
            'native_frame': frame, 'time_s': time_s,
            'source_kind': 'authored_native_request',
            'ego_center_xy_m': [6.5, 0], 'ego_front_yaw_deg': yaw,
            'ego_speed_mps': .5 if moving else 0,
            'native_road_id': 1, 'native_lane_id': -2})
        mapping.append({'video_frame': index, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time_s})
        bodies.append({'frame': frame, 'time_s': time_s,
            'native_road_id': 1, 'native_lane_id': -2,
            'body_vertices_m': [[6.5+dx, dy, .5] for dx, dy in
                                ((-.7,-.4),(-.7,.4),(.7,.4),(.7,-.4))]})
    write_rows(folder / 'native_samples.jsonl', samples)
    write_rows(folder / 'video_frames.jsonl', mapping)
    write_rows(folder / 'body_history.jsonl', bodies)
    return folder


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    results = {}
    for suffix, yaw, expected in (('probe_a', 45, 'front_with_lawful_flow'),
                                  ('probe_b', 225, 'front_against_lawful_flow')):
        case = FOLDER.name + '__' + suffix
        config = {'case_id': case, 'requested_front_yaw_deg': yaw}
        folder = source(case, yaw)
        positive = process(folder, config, allow_fixture=True)
        if positive['measurement']['direction'] != expected or \
                positive['city_permission_verified'] is not False or \
                positive['legal_verdict'] is not None:
            raise AssertionError('Positive orientation diagnostic differs')
        physical = assess(folder, config, allow_fixture=True)
        if physical['status'] != 'met' or physical['original_physical_completion_claimed']:
            raise AssertionError('Fixture physical preparation differs')
        moving = assess(source(case, yaw, moving=True), config, allow_fixture=True)
        if moving['status'] != 'not_met':
            raise AssertionError('Moving preparation negative failed')
        missing = SCRATCH / (suffix + '-missing')
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(folder, missing)
        (missing / 'permission_authority.json').unlink()
        try:
            process(missing, config, allow_fixture=True)
        except ValueError as exc:
            if 'Missing required source: permission_authority.json' not in str(exc):
                raise
        else:
            raise AssertionError('Missing permission source was accepted')
        for label, value in (('saved-positive', positive),
                             ('physical-positive', physical),
                             ('physical-moving-negative', moving)):
            write(HERE / (suffix + '-' + label + '.json'), value)
        results[suffix] = {'positive': expected, 'missing_permission_rejected': True,
                           'at_rest_met': True, 'moving_not_met': True}
    write(HERE / 'source-proof-receipt.json', {'format': 'c385967-source-proof-v1',
        'scope': 'synthetic CPU source-shaped diagnostics, not City permission or original Native acceptance',
        'cases': results})
    print(json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    main()
