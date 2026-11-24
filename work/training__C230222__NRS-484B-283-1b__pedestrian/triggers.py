"""Evaluate fallback decisions from source samples and a frame-aligned visibility audit.

Synthetic fixtures exercise decision logic. They are not physical trigger observations.
"""
import hashlib
import json
import math
from pathlib import Path

from engineering import candidate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure_source(folder, visibility_path):
    folder = Path(folder)
    samples = folder / 'curb-samples.jsonl'
    context = folder / 'curb-context.json'
    for path in (samples, context, Path(visibility_path)):
        if not path.is_file():
            raise ValueError('Missing trigger source: ' + path.name)
    rows = [json.loads(line) for line in samples.read_text().splitlines() if line.strip()]
    if len(rows) != 240:
        raise ValueError('Trigger requires 240 source frames')
    source = json.loads(context.read_text())
    if source.get('source_kind') not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Trigger source provenance missing')
    if source.get('curb_edge_xy_m') != [-3.5, 0]:
        raise ValueError('Trigger curb edge differs')
    first = rows[0]
    body = first.get('pedestrian_footprint_xy_m')
    if not isinstance(body, list) or len(body) != 4 or any(
        not isinstance(point, list) or len(point) != 2 or not all(map(_number, point))
        for point in body
    ):
        raise ValueError('Trigger initial footprint invalid')
    clearance = -3.5 - max(point[0] for point in body)
    if clearance < 0:
        raise ValueError('Trigger pedestrian already beyond curb')
    previous = None
    departure_acceleration = None
    for row in rows:
        if (type(row.get('native_frame')) is not int or
            not _number(row.get('time_s')) or
            not _number(row.get('pedestrian_speed_mps')) or
            row['pedestrian_speed_mps'] < 0):
            raise ValueError('Trigger frame or speed invalid')
        if previous is not None:
            if (row['native_frame'] != previous['native_frame'] + 1 or
                abs(row['time_s'] - previous['time_s'] - .05) > .002):
                raise ValueError('Trigger frame cadence differs')
            if (departure_acceleration is None and
                previous['pedestrian_speed_mps'] <= .05 and
                row['pedestrian_speed_mps'] > .05):
                departure_acceleration = ((row['pedestrian_speed_mps'] -
                    previous['pedestrian_speed_mps']) /
                    (row['time_s'] - previous['time_s']))
        previous = row
    if departure_acceleration is None:
        raise ValueError('Trigger departure not bracketed')
    visibility_path = Path(visibility_path)
    visibility = json.loads(visibility_path.read_text())
    if visibility.get('source_kind') not in (
        'synthetic_visibility_fixture', 'independent_original_pixel_audit'
    ) or visibility.get('curb_samples_sha256') != sha(samples):
        raise ValueError('Trigger visibility provenance differs')
    frames = visibility.get('frames')
    if not isinstance(frames, list) or len(frames) != 240:
        raise ValueError('Trigger visibility requires 240 frame joins')
    visible = 0
    for row, frame in zip(rows, frames):
        if (not isinstance(frame, dict) or
            frame.get('native_frame') != row['native_frame'] or
            not _number(frame.get('time_s')) or
            abs(frame['time_s'] - row['time_s']) > .002 or
            type(frame.get('curb_visible')) is not bool or
            type(frame.get('vehicle_visible')) is not bool):
            raise ValueError('Trigger visibility frame join differs')
        if visibility['source_kind'] == 'independent_original_pixel_audit' and not frame.get('rgb_sha256'):
            raise ValueError('Trigger original pixel hash missing')
        visible += frame['curb_visible'] and frame['vehicle_visible']
    return {'source_kind': source['source_kind'],
            'visibility_kind': visibility['source_kind'],
            'source_sha256': {'curb-samples.jsonl': sha(samples),
                              'curb-context.json': sha(context),
                              'visibility.json': sha(visibility_path)},
            'initial_footprint_clearance_m': round(clearance, 6),
            'first_departure_acceleration_mps2': round(departure_acceleration, 6),
            'curb_and_vehicle_visibility_fraction': visible / 240,
            'frames': 240, 'physical_trigger_observed': False}


def decide(suffix, measured):
    if suffix not in ('probe_1', 'probe_2'):
        raise ValueError('Unknown curb probe')
    metrics = {
        'fallback1': 'initial_footprint_clearance_m',
        'fallback2': 'first_departure_acceleration_mps2',
        'fallback3': 'curb_and_vehicle_visibility_fraction',
    }
    selected = []
    for ident, metric in metrics.items():
        value = measured[metric]
        threshold = candidate(suffix, ident)['trigger']['threshold']
        if not _number(value):
            raise ValueError('Trigger metric invalid: ' + metric)
        active = value < threshold if ident in ('fallback1', 'fallback3') else value > threshold
        if active:
            selected.append(ident)
    return {'case_suffix': suffix, 'activated_fallbacks': selected,
            'decisions': {ident: {'metric': metric, 'value': measured[metric],
                                  'threshold': candidate(suffix, ident)['trigger']['threshold'],
                                  'activate': ident in selected}
                          for ident, metric in metrics.items()},
            'physical_trigger_observed': False}
