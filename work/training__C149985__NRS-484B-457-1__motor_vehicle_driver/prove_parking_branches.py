"""CPU source-shape checks for default, left-curb and angle branches."""

import copy
import hashlib
import json

from measure_parking import CAMERAS, measure

H = hashlib.sha256(b'authoring-only-diagnostic').hexdigest()


def fixture(kind, gap_in=18, heading_deg=0):
    context = {'source_kind': 'synthetic_native_sample', 'parking_kind': kind,
               'highway_has_adjacent_curbs': True, 'one_way_highway': True,
               'right_curb_y_m': -4, 'left_curb_y_m': 4,
               'dot_maintained_highway': kind == 'angle_dot'}
    for key in ('native_map', 'curb_geometry', 'wheel_geometry', 'body_motion',
                'rest_state', 'camera_manifest'):
        context[key + '_sha256'] = H
    if kind == 'left_ordinance':
        context['local_left_ordinance_status'] = 'pending_original'
        context['left_ordinance_sha256'] = H
    if kind.startswith('angle'):
        context['local_angle_ordinance_status'] = 'pending_original'
        context['angle_ordinance_sha256'] = H
        context['dot_highway_designation_sha256'] = H
    if kind == 'angle_dot':
        context['dot_width_determination_status'] = 'pending_original'
        context['dot_width_determination_sha256'] = H
    gap_m = gap_in * .0254
    rows = []
    for i in range(600):
        rows.append({'video_frame': i, 'native_frame': i + 100,
                     'time_s': i / 20, 'source_cameras': {name: i for name in CAMERAS},
                     'ego_speed_mps': 2 if i < 240 else 0,
                     'stopped_or_parked': i >= 240,
                     'right_front_wheel_outer_y_m': -4 + gap_m,
                     'right_rear_wheel_outer_y_m': -4 + gap_m,
                     'left_front_wheel_outer_y_m': 4 - gap_m,
                     'left_rear_wheel_outer_y_m': 4 - gap_m,
                     'ego_heading_deg': heading_deg, 'curb_heading_deg': 0})
    return context, rows


def reject(context, rows, expected):
    try:
        measure(context, rows)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(str(exc)) from exc
        return str(exc)
    raise AssertionError('Missing-source mutation passed')


def main():
    positives = {}
    for suffix, kind, gap, angle in (
            ('right_16_parked', 'default_right', 16, 0),
            ('right_18_parked', 'default_right', 18, 0),
            ('right_20_parked', 'default_right', 20, 0),
            ('right_18_stopped', 'default_right', 18, 0),
            ('left_18_ordinance', 'left_ordinance', 18, 0),
            ('angle_ordinary', 'angle_ordinary', 18, 45),
            ('angle_dot', 'angle_dot', 18, 45)):
        context, rows = fixture(kind, gap, angle)
        positives[suffix] = measure(context, rows)
    negatives = {}
    context, rows = fixture('default_right')
    m = copy.deepcopy(context); m.pop('curb_geometry_sha256')
    negatives['missing_curb'] = reject(m, rows, 'curb_geometry')
    m = copy.deepcopy(rows); m[17]['source_cameras'].pop('overview')
    negatives['missing_camera'] = reject(context, m, 'camera')
    m = copy.deepcopy(rows); m[300]['stopped_or_parked'] = False
    m = m[:240] + m[300:]
    negatives['missing_duration'] = reject(context, m, 'Incomplete')
    context, rows = fixture('left_ordinance')
    m = copy.deepcopy(context); m.pop('left_ordinance_sha256')
    negatives['missing_left_ordinance'] = reject(m, rows, 'left_ordinance')
    m = copy.deepcopy(context); m['source_kind'] = 'original_native_parking_readback'
    negatives['unsourced_original_authority'] = reject(m, rows, 'authority review pending')
    context, rows = fixture('angle_dot')
    m = copy.deepcopy(context); m.pop('dot_width_determination_sha256')
    negatives['missing_dot_determination'] = reject(m, rows, 'dot_width_determination')
    m = copy.deepcopy(context); m['dot_maintained_highway'] = False
    negatives['wrong_dot_designation'] = reject(m, rows, 'DOT highway designation')
    return {'format': 'worker-c149985-parking-branch-diagnostic', 'passed': True,
            'positives': positives, 'negative_rejections': negatives,
            'synthetic_diagnostic_only': True, 'ordinance_authority_verified': False,
            'dot_determination_verified': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
