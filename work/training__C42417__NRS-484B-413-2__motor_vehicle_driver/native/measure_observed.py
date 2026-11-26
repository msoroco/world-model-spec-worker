"""Measure preturn signaling from retained Native samples, never from requests."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CASE_PREFIX = 'training__C42417__NRS-484B-413-2__motor_vehicle_driver__selected_c8ca9085__condition_'


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Nonfinite or missing Native measurement')
    return float(value)


def measure(path: Path, case_id: str, *, allow_fixture: bool = False) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: native_samples.jsonl')
    if case_id not in (CASE_PREFIX + 'a', CASE_PREFIX + 'b'):
        raise ValueError('Exact selected case differs')
    lines = path.read_text().splitlines()
    if len(lines) != FRAMES:
        raise ValueError('Incomplete 600-frame Native sample window')
    rows = [json.loads(line) for line in lines]
    provenance = {row.get('provenance') for row in rows}
    if provenance == {'synthetic_cpu_fixture'} and allow_fixture:
        synthetic = True
    elif provenance == {'original_native_capture'}:
        synthetic = False
    else:
        raise ValueError('Original Native source provenance missing')
    if any(row.get('case_id') != case_id for row in rows):
        raise ValueError('Exact Native case join differs')
    if {row.get('area_classification') for row in rows} != {'business_district'}:
        raise ValueError('Business-district source context missing')
    weather = {row.get('precipitation') for row in rows}
    if len(weather) != 1 or None in weather:
        raise ValueError('Native weather source context missing')
    path_length = 0.0
    previous_xy = None
    previous_native_frame = -1
    previous_time = -math.inf
    distances = []
    for frame, row in enumerate(rows):
        native_frame = row.get('native_frame')
        if type(native_frame) is not int or native_frame <= previous_native_frame or row.get('sample_index') != frame:
            raise ValueError('Native frame join differs')
        previous_native_frame = native_frame
        time = _finite(row.get('time_s'))
        if time <= previous_time or (frame and abs(time - previous_time - 1 / RATE_HZ) > 1e-3):
            raise ValueError('Native timestamp join differs')
        previous_time = time
        xy = row.get('ego_center_xy_m')
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError('Original ego position source missing')
        xy = tuple(_finite(value) for value in xy)
        if previous_xy is not None:
            step = math.dist(previous_xy, xy)
            if step > 2.0:
                raise ValueError('Implausible Native position jump')
            path_length += step
        previous_xy = xy
        distances.append(path_length)
        _finite(row.get('ego_heading_deg'))
        _finite(row.get('ego_speed_mps'))
        if not isinstance(row.get('right_lamp_observed'), bool):
            raise ValueError('Observed indicator source missing')
        if not isinstance(row.get('right_lamp_commanded'), bool):
            raise ValueError('Indicator command source missing')
        if not isinstance(row.get('course_change_observed'), bool):
            raise ValueError('Observed course-change source missing')
    changes = [i for i, row in enumerate(rows) if row['course_change_observed']]
    if not changes or changes[0] < 2 or changes[0] >= FRAMES - 2:
        raise ValueError('Observed course-change onset missing')
    onset = changes[0]
    if any(row['course_change_observed'] for row in rows[:onset]):
        raise ValueError('Course-change onset inconsistent')
    # Use the observed state of the right lamp, not the commanded signal.
    last_off = max((i for i in range(onset) if not rows[i]['right_lamp_observed']), default=-1)
    signal_onset = last_off + 1
    # An indicator already on at the first retained frame has no observed onset.
    # Its prior continuous distance is censored and cannot prove this threshold.
    continuous = 0 < signal_onset < onset and all(row['right_lamp_observed'] for row in rows[signal_onset:onset + 1])
    distance = distances[onset] - distances[signal_onset] if continuous else 0.0
    return {
        'format': 'c42417-observed-signal-distance-v1',
        'case_id': case_id,
        'source_path': path.name,
        'source_sha256': _sha(path),
        'source_kind': 'synthetic_cpu_fixture' if synthetic else 'original_native_capture',
        'original_native_observed': not synthetic,
        'sample_count': FRAMES,
        'rate_hz': RATE_HZ,
        'area_classification': 'business_district',
        'precipitation': weather.pop(),
        'signal_onset_frame': signal_onset if continuous else None,
        'course_change_onset_frame': onset,
        'continuous_observed_signal_distance_m': round(distance, 5),
        'business_100ft_distance_observed': continuous and distance >= 30.48,
        'weather_exception_applied': False,
        'physical_completion_claimed': False,
        'legal_verdict': None,
        'limitations': ['Business-district classification and lamp pixels require independent source review',
                        'Sampled indicator state does not alone establish visible flashing or legal compliance'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--allow-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(measure(args.source, args.case, allow_fixture=args.allow_fixture), indent=2))
