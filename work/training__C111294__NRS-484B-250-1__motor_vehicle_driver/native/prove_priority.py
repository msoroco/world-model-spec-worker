"""CPU-only diagnostic for source joins, precedence, and statutory context gates."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_priority import ASSIGNMENT, COUNT, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_lines(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def reject(source, expected):
    try:
        measure(source)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f'Wrong rejection: {exc}; wanted {expected}') from exc
        return str(exc)
    raise AssertionError('Invalid source was accepted: ' + expected)


def main():
    root = Path(__file__).resolve().parents[3]
    assignment_path = root / 'inputs' / ASSIGNMENT / 'assignment.json'
    assert assignment_path.is_file()
    with tempfile.TemporaryDirectory(prefix='priority-', dir=os.environ['TMPDIR']) as name:
        source = Path(name)
        for camera in ('forward', 'rear', 'left', 'right'):
            path = source / ('camera_' + camera + '.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=32x24:r=20',
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', '-y', str(path)], check=True)
        frames = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i * .05, 3)} for i in range(COUNT)]
        trace = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                  'ego_highway_id': 'south_highway', 'priority_highway_id': 'west_highway',
                  'ego_x_m': 0.0, 'ego_y_m': 0.0 if 300 <= i < 380 else -10.0,
                  'priority_x_m': 0.0 if 200 <= i < 340 else -10.0, 'priority_y_m': 0.0,
                  'ego_speed_mps': 0.0 if 200 <= i < 290 else 6.0,
                  'priority_speed_mps': 5.0} for i in range(COUNT)]
        context = {'assignment_id': ASSIGNMENT, 'review_kind': 'synthetic_diagnostic',
                   'reviewer': 'synthetic CPU diagnostic',
                   'camera_sha256': {p.name: sha(p) for p in source.glob('camera_*.mkv')},
                   'intersection_boundary_source': 'synthetic polygon fixture',
                   'route_origin_source': 'synthetic route fixture',
                   'device_review_source': 'synthetic device fixture',
                   'turn_intent_review_source': 'synthetic turn fixture',
                   'control_state_source': 'synthetic control fixture',
                   'ego_highway_id': 'south_highway', 'priority_highway_id': 'west_highway',
                   'intersection_bounds_xy_m': [-5.0, -5.0, 5.0, 5.0],
                   'official_device_controls_intersection': False, 'signal_inoperative': False,
                   'opposite_approaches': False, 'either_left_turning_or_intending': False}
        frame_path = source / 'video_frames.jsonl'
        trace_path = source / 'intersection_trace.jsonl'
        context_path = source / 'intersection_context.json'
        save_lines(frame_path, frames)
        save_lines(trace_path, trace)
        context_path.write_text(json.dumps(context))
        baseline = measure(source)
        assert baseline['priority_entry_video_frame'] == 200
        assert baseline['ego_entry_video_frame'] == 300
        assert baseline['priority_present_at_ego_entry']
        assert baseline['ego_min_speed_between_entries_mps'] == 0.0
        assert not baseline['device_exclusion_context']
        assert not baseline['opposite_left_turn_exclusion_context']
        cases = {'uncontrolled': baseline}
        for label, changes in {
            'controlled_device': {'official_device_controls_intersection': True, 'device_type': 'stop_sign'},
            'inoperative_signal': {'official_device_controls_intersection': True,
                                   'device_type': 'traffic_signal', 'signal_inoperative': True},
            'opposite_left_turn': {'opposite_approaches': True, 'either_left_turning_or_intending': True},
        }.items():
            context.update(changes)
            context_path.write_text(json.dumps(context))
            cases[label] = measure(source)
            context = {**context, **{k: False for k in ('official_device_controls_intersection',
                        'signal_inoperative', 'opposite_approaches', 'either_left_turning_or_intending')}}
            context.pop('device_type', None)
        assert cases['controlled_device']['device_exclusion_context']
        assert not cases['inoperative_signal']['device_exclusion_context']
        assert cases['opposite_left_turn']['opposite_left_turn_exclusion_context']
        context_path.write_text(json.dumps(context))
        failures = {}
        mutated = copy.deepcopy(context)
        mutated['priority_highway_id'] = 'south_highway'
        context_path.write_text(json.dumps(mutated))
        failures['same_highway'] = reject(source, 'different highway')
        mutated = copy.deepcopy(context)
        mutated['camera_sha256']['camera_forward.mkv'] = '0' * 64
        context_path.write_text(json.dumps(mutated))
        failures['unbound_camera'] = reject(source, 'camera bytes')
        mutated = copy.deepcopy(context)
        mutated.pop('device_review_source')
        context_path.write_text(json.dumps(mutated))
        failures['missing_device_review'] = reject(source, 'device_review_source')
        context_path.write_text(json.dumps(context))
        bad = copy.deepcopy(trace)
        for row in bad:
            row['priority_x_m'] = 0.0 if 350 <= row['video_frame'] < 450 else -10.0
        save_lines(trace_path, bad)
        failures['wrong_entry_order'] = reject(source, 'did not enter first')
        bad = copy.deepcopy(trace)
        bad[101]['native_frame'] = bad[100]['native_frame']
        save_lines(trace_path, bad)
        failures['frame_join'] = reject(source, 'frame map')
        bad = copy.deepcopy(trace)
        bad[101]['source_kind'] = 'original_native_pose'
        save_lines(trace_path, bad)
        failures['provenance'] = reject(source, 'provenance')
        save_lines(trace_path, trace)
        frame_path.unlink()
        failures['missing_frame_source'] = reject(source, 'video_frames.jsonl')
        print(json.dumps({'format': 'priority-cpu-proof', 'passed': True, 'assignment_id': ASSIGNMENT,
                          'assignment_sha256': sha(assignment_path),
                          'scenarios': {k: {'priority_entry': v['priority_entry_video_frame'],
                                            'ego_entry': v['ego_entry_video_frame'],
                                            'device_exclusion': v['device_exclusion_context'],
                                            'opposite_left_turn_exclusion': v['opposite_left_turn_exclusion_context']}
                                        for k, v in cases.items()},
                          'negative_rejections': failures,
                          'synthetic_only': True, 'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
