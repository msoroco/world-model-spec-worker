"""Saved-only source joins and measured signal distance, without legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from measure_observed import measure


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def process(attempt: Path, config: dict, *, allow_fixture: bool = False) -> dict:
    attempt = Path(attempt)
    source_names = ('native_samples.jsonl', 'video_frames.jsonl',
                    'body_history.jsonl', 'road_geometry.json', 'control_context.json')
    paths = {name: attempt / name for name in source_names}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
    samples = _rows(paths['native_samples.jsonl'])
    mapping = _rows(paths['video_frames.jsonl'])
    bodies = _rows(paths['body_history.jsonl'])
    if not all(len(items) == 600 for items in (samples, mapping, bodies)):
        raise ValueError('Original Native/body/video frame counts differ')
    for index, (sample, frame, body) in enumerate(zip(samples, mapping, bodies)):
        if frame.get('video_frame') != index or frame.get('native_frame') != sample.get('native_frame') or \
                body.get('frame') != sample.get('native_frame'):
            raise ValueError('Original Native/body/video frame join differs')
        if abs(float(frame.get('time_s')) - float(sample.get('time_s'))) > 1e-4 or \
                abs(float(body.get('time_s')) - float(sample.get('time_s'))) > 1e-4:
            raise ValueError('Original Native/body/video timestamp join differs')
        vertices = body.get('body_vertices_m')
        if not isinstance(vertices, list) or len(vertices) < 4 or \
                any(not isinstance(vertex, list) or len(vertex) != 3 for vertex in vertices):
            raise ValueError('Full original ego body source missing')
    geometry = json.loads(paths['road_geometry.json'].read_text())
    if geometry.get('area_classification') != 'business_district' or \
            geometry.get('area_classification_review_required') is not True or \
            not isinstance(geometry.get('native_map_sha256'), str) or \
            len(geometry['native_map_sha256']) != 64:
        raise ValueError('Original Native district/map source context missing')
    if geometry.get('provenance') == 'synthetic_cpu_fixture' and not allow_fixture:
        raise ValueError('Original Native district/map source provenance missing')
    if geometry.get('provenance') not in ('synthetic_cpu_fixture', 'original_native_capture'):
        raise ValueError('Original Native district/map source provenance missing')
    control = json.loads(paths['control_context.json'].read_text())
    if control.get('control') != 'other_vehicle' or \
            control.get('native_blueprint') != 'vehicle.lincoln.mkz_2020' or \
            type(control.get('native_actor_id')) is not int or \
            type(control.get('native_road_id')) is not int or \
            type(control.get('native_lane_id')) is not int or \
            control.get('stationary_opposing_lane_plan') is not True:
        raise ValueError('Original Native other-vehicle source context missing')
    if control['native_lane_id'] == control.get('approach_lane_id'):
        raise ValueError('Other vehicle occupies the ego lane')
    for row in samples:
        other = row.get('other_vehicle')
        if not isinstance(other, dict) or other.get('native_actor_id') != control['native_actor_id'] or \
                other.get('alive') is not True or \
                not isinstance(other.get('center_xy_m'), list) or len(other['center_xy_m']) != 2 or \
                any(type(value) not in (int, float) or not math.isfinite(value) for value in
                    (*other['center_xy_m'], other.get('heading_deg'), other.get('speed_mps'))):
            raise ValueError('Original Native other-vehicle frame source missing')
    measured = measure(paths['native_samples.jsonl'], config['case_id'],
                       allow_fixture=allow_fixture)
    if measured['source_kind'] != geometry['provenance']:
        raise ValueError('Native sample/map provenance differs')
    target = config['signal_distance_m']
    actual = measured['continuous_observed_signal_distance_m']
    return {'format': 'c42387-source-joined-saved-distance-v1',
            'case_id': config['case_id'], 'source_hashes': {name: sha(path)
                for name, path in paths.items()}, 'measurement': measured,
            'requested_signal_distance_m': target,
            'measured_signal_distance_m': actual,
            'request_match_within_1m_diagnostic': abs(target - actual) <= 1,
            'physical_completion_claimed': False, 'legal_verdict': None,
            'limitations': ['Original right-lamp pixels, legal business-district classification and physical route require independent review']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-fixture', action='store_true')
    args = parser.parse_args()
    result = process(args.attempt, json.loads(args.config.read_text()),
                     allow_fixture=args.allow_fixture)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
