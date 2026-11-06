"""Measure a parking-control act separately from a stationary facility stop.

This is an engineering observation. Facility designation, statutory exceptions,
and a legal parking determination require independent evidence.
"""
import hashlib
import json
import math
from pathlib import Path

from measure_facility import overlap_area, rectangle

RATE_HZ = 20
MIN_HELD_FRAMES = 40


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'park-act-sources.json').read_text())
    if manifest.get('format') != 'c10052-park-act-sources-v1':
        raise ValueError('Unknown parking source manifest')
    kind = manifest.get('source_kind')
    if kind not in ('synthetic_cpu_fixture', 'original_native'):
        raise ValueError('Parking source provenance unresolved')
    names = ('native_samples.jsonl', 'native_controls.jsonl', 'road_geometry.json')
    if set(manifest.get('sha256', {})) != set(names):
        raise ValueError('Incomplete parking source set')
    for name in names:
        if _sha(folder / name) != manifest['sha256'][name]:
            raise ValueError('Parking source hash differs: ' + name)
    poses, controls = _rows(folder / names[0]), _rows(folder / names[1])
    if len(poses) != 480 or len(controls) != len(poses):
        raise ValueError('Parking source frame count differs')
    geometry = json.loads((folder / names[2]).read_text())
    facility = rectangle(geometry.get('bicycle_facility_native_xy_bounds_m'), 'facility')
    held = []
    overlap = []
    last_frame = None
    last_time = None
    for pose, control in zip(poses, controls):
        frame, time = pose.get('native_frame'), pose.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Parking pose frame/time invalid')
        if last_frame is not None and (frame != last_frame + 1 or abs(time - last_time - 1/RATE_HZ) > .001):
            raise ValueError('Parking pose frame/time discontinuity')
        if control.get('native_frame') != frame or control.get('time_s') != time:
            raise ValueError('Parking control/pose join differs')
        if control.get('control_source') != ('synthetic_fixture' if kind == 'synthetic_cpu_fixture' else 'native_readback'):
            raise ValueError('Parking control source differs')
        synthetic = pose.get('synthetic_diagnostic') is True and control.get('synthetic_diagnostic') is True
        if (kind == 'synthetic_cpu_fixture') != synthetic:
            raise ValueError('Parking provenance differs')
        speed = pose.get('speed_mps')
        throttle = control.get('throttle')
        brake = control.get('brake')
        hand_brake = control.get('hand_brake')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (speed, throttle, brake)):
            raise ValueError('Parking speed/control invalid')
        if speed < 0 or not 0 <= throttle <= 1 or not 0 <= brake <= 1 or type(hand_brake) is not bool:
            raise ValueError('Parking speed/control outside domain')
        area = overlap_area(pose.get('native_body_xy_m'), facility)
        overlap.append(area)
        held.append(speed <= .1 and throttle <= .01 and hand_brake and area > .01)
        last_frame, last_time = frame, time
    intervals = []
    start = None
    for i, flag in enumerate(held + [False]):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            if i - start >= MIN_HELD_FRAMES:
                intervals.append((start, i))
            start = None
    longest = max(intervals, key=lambda x: x[1]-x[0], default=None)
    return {
        'format': 'c10052-park-act-observation-v1',
        'source_kind': kind,
        'source_sha256': manifest['sha256'],
        'original_frame_count': len(poses),
        'park_control_candidate': longest is not None,
        'first_held_native_frame': None if longest is None else poses[longest[0]]['native_frame'],
        'held_duration_s': 0 if longest is None else round((longest[1]-longest[0])/RATE_HZ, 5),
        'max_held_facility_overlap_m2': 0 if longest is None else round(max(overlap[longest[0]:longest[1]]), 6),
        'facility_designation_verified': False,
        'statutory_exceptions_verified': False,
        'legal_park_verdict_claimed': False,
        'accepted': False,
    }
