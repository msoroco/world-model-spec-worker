"""Independent audit of saved C111331 request sources.

The fixture path reports construction requests only. It cannot establish a
physical stop, a truly inoperative signal, or a legal conclusion.
"""
import argparse
import hashlib
import json
from pathlib import Path

BASE = 'training__C111331__NRS-484B-250-4__motor_vehicle_driver'
REQUIRED = ('vehicle-history.jsonl', 'signal-context.json', 'trace.jsonl',
            'video_frames.jsonl', 'capture/evidence.jsonl', 'road.xodr')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def inspect(source, suffix):
    source = Path(source)
    for name in REQUIRED:
        if not (source / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = json.loads((source / 'signal-context.json').read_text())
    if (context.get('source_kind') != 'synthetic_cpu_diagnostic' or
            context.get('official_signal_state_verified') is not False or
            context.get('physical_stop_verified') is not False or
            context.get('yielding_verified') is not False or
            context.get('marked_stop_line_x_m') != -26 or
            context.get('near_side_crosswalk_x_m') != -23 or
            context.get('intersection_entry_x_m') != -20):
        raise ValueError('Source classification or stop-point context differs')
    rows = read_rows(source / 'vehicle-history.jsonl')
    trace = read_rows(source / 'trace.jsonl')
    video = read_rows(source / 'video_frames.jsonl')
    evidence = read_rows(source / 'capture/evidence.jsonl')
    if any(len(items) != 600 for items in (rows, trace, video, evidence)):
        raise ValueError('Complete 600-frame source join required')
    stationary = 0
    crossing = None
    for i, (row, pose, mapping, native) in enumerate(zip(rows, trace, video, evidence)):
        if (row.get('frame') != i or pose.get('frame') != i or
                mapping.get('native_frame') != i or native.get('original_frame') != i or
                any(abs(item.get('time_s', -100) - i / 20) > 1e-6
                    for item in (row, pose, mapping)) or
                abs(native.get('recording_time_s', -100) - i / 20) > 1e-6):
            raise ValueError('Original frame/time join differs')
        if (row.get('source_kind') != 'construction_request' or
                row.get('native_observed') is not False or
                row.get('legal_verdict') is not None or
                row.get('signal_installed_requested') is not True or
                row.get('signal_uncovered_requested') is not True or
                row.get('signal_display_requested') != 'inoperative_dark' or
                row.get('signal_id') != context['signal_id'] or
                (row.get('marked_stop_line_x_m'), row.get('near_side_crosswalk_x_m'),
                 row.get('intersection_entry_x_m')) != (-26, -23, -20)):
            raise ValueError('Authored signal or stop-point source differs')
        if (abs(row['ego_front_x_m'] - row['ego_center_xy_m'][0] - 2) > 1e-6 or
                abs(pose['position_m'][0] - row['ego_center_xy_m'][0]) > 1e-6 or
                abs(native['ego']['position_m'][0] - row['ego_center_xy_m'][0]) > 1e-6):
            raise ValueError('Body, trace or Native source position differs')
        if i and row['ego_center_xy_m'] == rows[i - 1]['ego_center_xy_m'] and row['ego_front_x_m'] < -26:
            stationary += 1
        if crossing is None and row['ego_front_x_m'] >= -26:
            crossing = i
    if crossing is None:
        raise ValueError('Missing marked-line crossing')
    return {'case_id': BASE + '__' + suffix, 'frames': 600,
            'pre_line_stationary_frames': stationary,
            'first_stop_line_cross_frame': crossing,
            'sources': {name: digest(source / name) for name in REQUIRED},
            'rows': rows}


def compare(primary, contrast):
    a, b = inspect(primary, 'controlled_1'), inspect(contrast, 'controlled_2')
    for left, right in zip(a.pop('rows'), b.pop('rows')):
        fixed = ('other_center_xy_m', 'signal_id', 'signal_installed_requested',
                 'signal_uncovered_requested', 'signal_display_requested',
                 'marked_stop_line_x_m', 'near_side_crosswalk_x_m',
                 'intersection_entry_x_m')
        if any(left[key] != right[key] for key in fixed):
            raise ValueError('Fixed comparison condition changed')
    if (a['pre_line_stationary_frames'] <= 0 or b['pre_line_stationary_frames'] != 0 or
            a['first_stop_line_cross_frame'] <= b['first_stop_line_cross_frame']):
        raise ValueError('Requested stop/no-stop contrast differs')
    return {'format': 'worker-source-comparison-audit-v1', 'cases': [a, b],
            'fixed_conditions_checked': True, 'requested_difference_checked': True,
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--primary', required=True)
    parser.add_argument('--contrast', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(compare(args.primary, args.contrast), indent=2) + '\n')
