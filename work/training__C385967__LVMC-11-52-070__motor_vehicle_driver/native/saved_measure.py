"""Validate saved angle-parking sources; report direction without a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from angle_park import measure

NAMES = ('native_samples.jsonl', 'video_frames.jsonl', 'body_history.jsonl',
         'road_geometry.json', 'parking_context.json', 'permission_authority.json',
         'permission-source.bin')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def process(attempt, config, *, allow_fixture=False):
    attempt = Path(attempt)
    paths = {name: attempt / name for name in NAMES}
    for name, path in paths.items():
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing required source: ' + name)
    samples, mapping, bodies = (rows(paths[name]) for name in NAMES[:3])
    if any(len(items) != 600 for items in (samples, mapping, bodies)):
        raise ValueError('Full 600-frame Native/body/video source required')
    geometry = json.loads(paths['road_geometry.json'].read_text())
    context = json.loads(paths['parking_context.json'].read_text())
    permission = json.loads(paths['permission_authority.json'].read_text())
    provenance = geometry.get('provenance')
    if provenance not in ('original_native_capture', 'synthetic_cpu_fixture') or \
            (provenance == 'synthetic_cpu_fixture' and not allow_fixture):
        raise ValueError('Original Native map provenance missing')
    if geometry.get('lawful_traffic_heading_deg') != 90 or \
            geometry.get('bay_center_xy_m') != [6.5, 0] or \
            geometry.get('sign_or_marking_readback_review_required') is not True or \
            len(str(geometry.get('native_map_sha256', ''))) != 64:
        raise ValueError('Native bay, lawful direction or marking source missing')
    if context.get('control') != 'angle_parking_designation' or \
            context.get('native_parking_lane_id') != geometry.get('parking_lane_id') or \
            context.get('native_road_id') != geometry.get('native_road_id') or \
            context.get('requested_activity') != 'standing_or_parked' or \
            context.get('actual_activity_and_bay_containment_review_required') is not True:
        raise ValueError('Original standing or parked activity context missing')
    if permission.get('source_file') != 'permission-source.bin' or \
            permission.get('source_sha256') != sha(paths['permission-source.bin']) or \
            permission.get('authority_claim') != 'City Traffic Engineer' or \
            permission.get('permission_verified') is not False or \
            permission.get('authored_sign_not_permission_evidence') is not True or \
            permission.get('independent_authority_and_street_review_required') is not True:
        raise ValueError('Independent City Traffic Engineer permission source missing')
    if provenance == 'synthetic_cpu_fixture' and permission.get('source_kind') != 'synthetic_cpu_fixture':
        raise ValueError('Fixture cannot claim original City permission')
    if provenance == 'original_native_capture' and permission.get('source_kind') != 'original_external_document':
        raise ValueError('Original permission document provenance missing')
    for index, (sample, frame, body) in enumerate(zip(samples, mapping, bodies)):
        native_frame = sample.get('native_frame')
        if (sample.get('case_id') != config['case_id'] or sample.get('frame') != index or
            sample.get('sample_index') != index or frame.get('video_frame') != index or
            frame.get('native_frame') != native_frame or body.get('frame') != native_frame or
            sample.get('native_road_id') != geometry['native_road_id'] or
            sample.get('native_lane_id') != geometry['parking_lane_id'] or
            body.get('native_road_id') != geometry['native_road_id'] or
            body.get('native_lane_id') != geometry['parking_lane_id']):
            raise ValueError('Original Native/body/video frame or lane join differs')
        if any(abs(float(item.get('time_s', -1)) - float(sample['time_s'])) > .001
               for item in (frame, body)):
            raise ValueError('Original Native/body/video time join differs')
        vertices = body.get('body_vertices_m')
        if not isinstance(vertices, list) or len(vertices) < 4 or any(
                not isinstance(vertex, list) or len(vertex) != 3 or any(
                    type(value) not in (int, float) or not math.isfinite(value)
                    for value in vertex) for vertex in vertices):
            raise ValueError('Original parked body vertices missing')
    kind = 'original_native' if provenance == 'original_native_capture' else 'authored_native_request'
    direction = measure(samples, kind)
    return {'format': 'c385967-saved-orientation-v1', 'case_id': config['case_id'],
            'source_hashes': {name: sha(path) for name, path in paths.items()},
            'measurement': direction, 'source_kind': provenance,
            'city_permission_verified': False, 'sign_or_marking_review_required': True,
            'physical_completion_claimed': False, 'legal_verdict': None,
            'limitations': ['City Traffic Engineer authorization and street require independent review',
                            'Original marking, activity, body containment and video require independent review']}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-fixture', action='store_true')
    a = p.parse_args()
    value = process(a.attempt, json.loads(a.config.read_text()), allow_fixture=a.allow_fixture)
    a.output.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
