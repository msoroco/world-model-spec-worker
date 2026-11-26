"""Measure parking geometry without deciding ordinance authority or legal compliance."""

import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}
KINDS = {'default_right', 'left_ordinance', 'angle_ordinary', 'angle_dot'}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid ' + name)
    return float(value)


def source_hash(context, name):
    value = context.get(name + '_sha256')
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Missing source hash: ' + name)


def measure(context, rows):
    kind = context.get('parking_kind')
    if kind not in KINDS:
        raise ValueError('Unknown parking kind')
    if context.get('source_kind') not in ('original_native_parking_readback', 'synthetic_native_sample'):
        raise ValueError('Original or declared diagnostic source missing')
    for name in ('native_map', 'curb_geometry', 'wheel_geometry', 'body_motion',
                 'rest_state', 'camera_manifest'):
        source_hash(context, name)
    if context.get('highway_has_adjacent_curbs') is not True:
        raise ValueError('Adjacent curbs not established')
    if context.get('one_way_highway') is not True:
        raise ValueError('One-way highway not established')
    if kind == 'left_ordinance':
        if context.get('local_left_ordinance_status') not in ('verified', 'pending_original'):
            raise ValueError('Left-curb ordinance applicability missing')
        source_hash(context, 'left_ordinance')
    if kind in ('angle_ordinary', 'angle_dot'):
        if context.get('local_angle_ordinance_status') not in ('verified', 'pending_original'):
            raise ValueError('Angle ordinance applicability missing')
        source_hash(context, 'angle_ordinance')
        source_hash(context, 'dot_highway_designation')
        if context.get('dot_maintained_highway') is not (kind == 'angle_dot'):
            raise ValueError('DOT highway designation conflicts with case')
    if kind == 'angle_dot':
        if context.get('dot_width_determination_status') not in ('verified', 'pending_original'):
            raise ValueError('DOT width determination missing')
        source_hash(context, 'dot_width_determination')
    if len(rows) != FRAMES:
        raise ValueError('Incomplete 30-second source trace')
    curb_y = finite(context.get('left_curb_y_m' if kind == 'left_ordinance' else 'right_curb_y_m'), 'curb position')
    previous = None
    rest = []
    front = []
    rear = []
    heading = []
    for i, row in enumerate(rows):
        if row.get('video_frame') != i or row.get('source_cameras') != {name: i for name in CAMERAS}:
            raise ValueError('Four-camera source join failed')
        native = row.get('native_frame')
        if type(native) is not int or (previous is not None and native <= previous):
            raise ValueError('Native frame identity gap')
        previous = native
        if abs(finite(row.get('time_s'), 'time') - i / RATE_HZ) > 1e-6:
            raise ValueError('Native time join failed')
        speed = finite(row.get('ego_speed_mps'), 'speed')
        if speed < 0:
            raise ValueError('Negative speed')
        if row.get('stopped_or_parked') is True and speed <= .1:
            side = 'left' if kind == 'left_ordinance' else 'right'
            fy = finite(row.get(side + '_front_wheel_outer_y_m'), 'front wheel')
            ry = finite(row.get(side + '_rear_wheel_outer_y_m'), 'rear wheel')
            if kind != 'left_ordinance':
                gaps = (fy - curb_y, ry - curb_y)
            else:
                gaps = (curb_y - fy, curb_y - ry)
            if min(gaps) < 0:
                raise ValueError('Wheel beyond curb')
            delta = abs(((finite(row.get('ego_heading_deg'), 'heading') -
                          finite(row.get('curb_heading_deg'), 'curb heading') + 180) % 360) - 180)
            rest.append(i)
            front.append(gaps[0] * 39.37007874015748)
            rear.append(gaps[1] * 39.37007874015748)
            heading.append(delta)
    if not rest:
        raise ValueError('Stopped or parked interval missing')
    if context['source_kind'] == 'original_native_parking_readback':
        for field in ('local_left_ordinance_status', 'local_angle_ordinance_status',
                      'dot_width_determination_status'):
            if field in context and context[field] == 'pending_original':
                raise ValueError('Original administrative authority review pending')
    return {'format': 'worker-source-parking-measurement', 'parking_kind': kind,
            'frame_count': FRAMES, 'rest_frames': len(rest), 'first_rest_frame': rest[0],
            'front_wheel_gap_in_min': min(front), 'front_wheel_gap_in_max': max(front),
            'rear_wheel_gap_in_min': min(rear), 'rear_wheel_gap_in_max': max(rear),
            'maximum_heading_difference_deg': max(heading),
            'administrative_authority': {k: context.get(k) for k in
                ('local_left_ordinance_status', 'local_angle_ordinance_status',
                 'dot_width_determination_status')},
            'legal_compliance': 'unassessed', 'original_native_observed':
                context['source_kind'] == 'original_native_parking_readback'}
