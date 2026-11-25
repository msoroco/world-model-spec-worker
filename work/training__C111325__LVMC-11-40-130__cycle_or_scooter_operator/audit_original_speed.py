"""Independent original-source audit for the paired bicycle speed attempts.

Mock rows exercise the code only. Actual delivery requires original Native
provenance, sealed source hashes, physical review and the delivery auditor.
"""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def audit(trace_path, frames_path, context_path, diagnostic=False):
    rows, mapping = read_rows(trace_path), read_rows(frames_path)
    context = json.loads(Path(context_path).read_text())
    if len(rows) != FRAMES or len(mapping) != FRAMES:
        raise ValueError('Missing complete original bicycle or camera trace')
    expected_kind = 'synthetic_native_mock' if diagnostic else 'original_native_actor_readback'
    if (context.get('source_kind') != expected_kind or
            context.get('cell_id') != 'C111325' or
            context.get('law_id') != 'LVMC-11-40-130' or
            context.get('actor') != 'cycle_or_scooter_operator' or
            context.get('bicycle_blueprint') != 'vehicle.bh.crossbike' or
            context.get('stop_sign_governs_route') is not True or
            context.get('approach_lane_verified') is not True or
            context.get('municipal_jurisdiction_review_pending') is not True or
            context.get('legal_prudence_verdict') is not None):
        raise ValueError('Missing bicycle law or Native approach context')
    fixed_id = context.get('fixed_conditions_id')
    if not isinstance(fixed_id, str) or not fixed_id:
        raise ValueError('Missing comparison fixed-conditions identity')
    positions, speeds, first_stop = [], [], None
    actor_id, condition = None, None
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        if (row.get('sample_index') != index or frame.get('video_frame') != index or
                row.get('native_frame') != frame.get('native_frame') or
                row.get('time_s') != frame.get('time_s') or
                row.get('source_kind') != expected_kind or
                row.get('blueprint') != 'vehicle.bh.crossbike' or
                row.get('legal_verdict') is not None or
                row.get('fixed_conditions_id') != fixed_id or
                set(frame.get('camera_native_frames', {})) != set(CAMERAS) or
                any(v != row.get('native_frame') for v in
                    frame['camera_native_frames'].values())):
            raise ValueError('Bicycle source or four-camera frame join changed')
        if index and (row['native_frame'] <= rows[index-1]['native_frame'] or
                      row['time_s'] <= rows[index-1]['time_s']):
            raise ValueError('Original Native frame sequence changed')
        if actor_id is None:
            actor_id = row.get('actor_id')
            condition = row.get('condition')
        if (type(actor_id) is not int or row.get('actor_id') != actor_id or
                condition not in ('condition_a', 'condition_b') or
                row.get('condition') != condition):
            raise ValueError('Bicycle actor or speed condition changed')
        point = row.get('center_xy_m')
        velocity = row.get('velocity_xy_mps')
        if (not isinstance(point, list) or len(point) != 2 or
                not isinstance(velocity, list) or len(velocity) != 2 or
                not all(_finite(v) for v in point + velocity)):
            raise ValueError('Missing finite bicycle pose or velocity')
        if abs(point[1] + 1.75) > .65 or point[0] > -1.8:
            raise ValueError('Bicycle departed approach or crossed stop position')
        if index and point[0] + .03 < positions[-1][0]:
            raise ValueError('Bicycle reversed on stop approach')
        positions.append(point)
        speeds.append(math.hypot(*velocity))
        if first_stop is None and index > 0 and speeds[-1] < .2 and point[0] > -3:
            first_stop = index
    if first_stop is None:
        raise ValueError('Original bicycle stop was not observed')
    if positions[-1][0] < -3 or max(speeds) < 1:
        raise ValueError('Bicycle approach motion was not realized')
    return {'format': 'c111325-original-bicycle-speed-audit-v1',
            'condition': condition, 'actor_id': actor_id, 'frames': FRAMES,
            'first_stopped_frame': first_stop,
            'measured_peak_speed_mps': round(max(speeds), 6),
            'measured_position_span_m': round(positions[-1][0]-positions[0][0], 6),
            'fixed_conditions_id': fixed_id, 'trace_sha256': sha(trace_path),
            'frame_map_sha256': sha(frames_path),
            'context_sha256': sha(context_path),
            'diagnostic_only': diagnostic, 'legal_prudence_verdict': None,
            'physical_acceptance_claimed': False}


def compare(a, b):
    if a['condition'] != 'condition_a' or b['condition'] != 'condition_b':
        raise ValueError('Expected ordered slow and fast bicycle conditions')
    if a['fixed_conditions_id'] != b['fixed_conditions_id']:
        raise ValueError('Bicycle comparison changed fixed conditions')
    if a['measured_peak_speed_mps'] >= b['measured_peak_speed_mps']:
        raise ValueError('Bicycle speed contrast was not realized')
    if a['first_stopped_frame'] <= b['first_stopped_frame']:
        raise ValueError('Stop timing contrast was not realized')
    return {'passed': True, 'measured_speed_contrast_mps': round(
        b['measured_peak_speed_mps']-a['measured_peak_speed_mps'], 6),
        'fixed_conditions_id': a['fixed_conditions_id'],
        'legal_prudence_verdict': None,
        'physical_acceptance_claimed': False}
