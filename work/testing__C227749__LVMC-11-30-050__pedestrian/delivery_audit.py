"""Independent source checks for a saved pedestrian crossing attempt.

This intentionally cannot certify physical visibility or legal compliance.
"""
from __future__ import annotations

import math
from crossing_geometry import measure_original_history, point

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def audit_saved(scene, walker_rows, frame_joins, camera_sources, *, expected_camera_kind='original_native'):
    if set(camera_sources) != set(CAMERAS):
        raise ValueError('four exact camera sources required')
    for name, source in camera_sources.items():
        if not isinstance(source, dict) or source.get('kind') != expected_camera_kind or not source.get('sha256'):
            raise ValueError(f'{name}: original camera hash required')
    measured = measure_original_history(walker_rows, scene)
    frames = [row['frame'] for row in walker_rows]
    if frames != list(range(frames[0], frames[-1]+1)):
        raise ValueError('original walker frames must be contiguous')
    times = [row.get('time_s') for row in walker_rows]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times):
        raise ValueError('original time missing or nonfinite')
    if any(abs((b-a)-0.05) > 0.001 for a, b in zip(times, times[1:])):
        raise ValueError('original frame cadence is not 20 Hz')
    if len(frame_joins) != len(walker_rows):
        raise ValueError('camera frame join length differs from walker history')
    for row, join in zip(walker_rows, frame_joins):
        if join.get('frame') != row['frame'] or abs(join.get('time_s', float('inf'))-row['time_s']) > 0.001:
            raise ValueError('camera and walker original frame join mismatch')
        if set(join.get('cameras', {})) != set(CAMERAS):
            raise ValueError('four camera frame joins required')
        for value in join['cameras'].values():
            if isinstance(value, dict):
                if value.get('frame') != row['frame']:
                    raise ValueError('invalid camera original frame')
            elif type(value) is not int or value < 0:
                raise ValueError('invalid camera frame index')
    measured['audit_kind'] = 'saved_source_structure'
    measured['physical_visibility'] = 'unconfirmed'
    return measured
