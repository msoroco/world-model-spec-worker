"""Saved-only finalization for a compatible opposing-left exact case."""

import argparse
from hashlib import sha256
import json
from math import atan2, cos, hypot, sin
from pathlib import Path

from opposing_left_measurement import measure_opposing_left as _measure_opposing_left
from opposing_left_runner import check_config


def _source(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_opposing_left(root):
    return _measure_opposing_left(root)


def analyze(attempt):
    root = Path(attempt)
    config_path, _ = _source(root, 'config.json')
    config = json.loads(config_path.read_text())
    check_config(config)
    map_path, map_sha = _source(root, 'video_frames.jsonl')
    trace_path, trace_sha = _source(root, 'trace.jsonl')
    participant_path, participant_sha = _source(root, 'opposing_left_participants.jsonl')
    context_path, context_sha = _source(root, 'opposing_left_context.json')
    context = json.loads(context_path.read_text())
    expected_role = 'opposite' if config['cell_id'] == 'C111294' else 'turning'
    if context.get('subject_role', 'turning') != expected_role or (
            context.get('subject_actor_id', context.get('turning_actor_id')) !=
            context.get(expected_role + '_actor_id')):
        raise ValueError('Opposing-left original subject role differs from exact cell')
    if expected_role == 'opposite':
        route = context.get('opposite_route') or []
        if len(route) < 2 or not all('heading_xy' in node for node in
                                     (route[0], route[-1])):
            raise ValueError('Traveling subject original route heading missing')
        first, last = route[0]['heading_xy'], route[-1]['heading_xy']
        if first[0] * last[0] + first[1] * last[1] < .8:
            raise ValueError('Traveling subject original route turns at junction')
    mapping, trace, participants = (_rows(path) for path in
                                    (map_path, trace_path, participant_path))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(participants):
        raise ValueError('Opposing-left original source/frame-map length differs')
    for index, (video, motion, participant) in enumerate(zip(mapping, trace, participants)):
        identity = video.get('carla_frame'), video.get('time_s')
        if (video.get('video_frame') != index or
                (motion.get('frame'), motion.get('time_s')) != identity or
                (participant.get('frame'), participant.get('time_s')) != identity):
            raise ValueError('Opposing-left original source/frame-map join failed')
        if expected_role == 'opposite':
            corners = participant.get('opposite_corners')
            position = motion.get('position_m')
            if (not isinstance(corners, list) or len(corners) != 4 or
                    not isinstance(position, list) or len(position) < 2):
                raise ValueError('Traveling subject original body/trace source missing')
            center = [sum(point[axis] for point in corners) / 4 for axis in (0, 1)]
            if hypot(center[0] - position[0], center[1] - position[1]) > .5:
                raise ValueError('Traveling subject original body differs from trace')
            heading = participant.get('opposite_heading_rad')
            trace_heading = motion.get('heading_deg')
            if not isinstance(heading, (int, float)) or not isinstance(trace_heading, (int, float)) or abs(atan2(sin(heading - trace_heading * 3.141592653589793 / 180), cos(heading - trace_heading * 3.141592653589793 / 180))) > .25:
                raise ValueError('Traveling subject original heading differs from trace')
    observed = measure_opposing_left(root)
    observed['sources']['trace.jsonl'] = trace_sha
    channel = root / 'channels' / 'opposing_left_participants.jsonl'
    channel.parent.mkdir(exist_ok=True)
    derived = ''.join(json.dumps({'time_s': row['time_s'], 'value': {
        'turning_actor_id': row['turning_actor_id'],
        'opposite_actor_id': row['opposite_actor_id'],
        'turning_corners': row['turning_corners'],
        'opposite_corners': row['opposite_corners'],
        'turning_heading_rad': row['turning_heading_rad'],
        'opposite_heading_rad': row['opposite_heading_rad']}}) + '\n'
        for row in participants)
    if channel.exists() and channel.read_text() != derived:
        raise ValueError('Derived opposing-left channel differs from original source')
    channel.write_text(derived)
    junction = [node['xy'] for route in (context['turning_route'], context['opposite_route'])
                for node in route if str(node.get('junction_id')) == str(context['junction_id'])]
    if len(junction) < 2:
        raise ValueError('Opposing-left original junction geometry missing')
    x0, x1 = min(point[0] for point in junction) - 2.5, max(point[0] for point in junction) + 2.5
    y0, y1 = min(point[1] for point in junction) - 2.5, max(point[1] for point in junction) + 2.5
    def occupied(corners):
        center = [sum(point[axis] for point in corners) / 4 for axis in (0, 1)]
        return x0 <= center[0] <= x1 and y0 <= center[1] <= y1
    occupancy = ''.join(json.dumps({'time_s': row['time_s'], 'value':
        occupied(row['turning_corners']) or occupied(row['opposite_corners'])}) + '\n'
        for row in participants)
    occupancy_view = root / 'channels' / 'intersection_occupancy.jsonl'
    if occupancy_view.exists() and occupancy_view.read_text() != occupancy:
        raise ValueError('Derived intersection occupancy differs from original source')
    occupancy_view.write_text(occupancy)
    context_view = root / 'channels' / 'opposing_left_context.json'
    context_record = json.dumps({'opposing_left_context': context}, sort_keys=True) + '\n'
    if context_view.exists() and context_view.read_text() != context_record:
        raise ValueError('Derived opposing-left context differs from original source')
    context_view.write_text(context_record)
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'measurements': {'opposing_left_observation': observed},
            'limitations': ['Original route and body motion do not establish a legal exception or physical completion.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict):
        raise ValueError('Selected opposing-left recording description missing')
    observed = report['measurements']['opposing_left_observation']['value']
    return {'case_id': config['selected_case_id'],
            'measured_values': {'opposing_left_observation': observed},
            'target_checks': [{'target': 'connected opposite approach and leftward turn',
                'requested': True,
                'measured': {'approach_heading_dot': observed['approach_heading_dot'],
                             'planned_left_cross': observed['planned_left_cross'],
                             'observed_turn_heading_change_rad': observed['observed_turn_heading_change_rad']},
                'method': 'original Native route and body heading join',
                'tolerance': None, 'matched': False,
                'physical_cause_confirmed': False,
                'cause_evidence': 'Original Native source; physical review pending'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved opposing-left measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': [name + '.mkv' for name in
                                 ('overview', 'approach', 'reference_corner', 'driver_reference')],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description,
            'recording_evidence': [
                {'name': 'opposing_left_context', 'unit': 'structured route',
                 'reference': 'channels/opposing_left_context.json',
                 'sha256': sha256((root / 'channels/opposing_left_context.json').read_bytes()).hexdigest()},
                {'name': 'opposing_left_participants', 'unit': 'm and rad',
                 'reference': 'channels/opposing_left_participants.jsonl',
                 'sha256': sha256((root / 'channels/opposing_left_participants.jsonl').read_bytes()).hexdigest()},
                {'name': 'intersection_occupancy', 'unit': 'bool',
                 'reference': 'channels/intersection_occupancy.jsonl',
                 'sha256': sha256((root / 'channels/intersection_occupancy.jsonl').read_bytes()).hexdigest()}],
            'realized_observables': {'turn_heading_change': {
                'unit': 'rad', 'method': 'first to last original turning actor heading',
                'time_window': 'full original trace', 'statistic': 'difference',
                'reference': 'opposing_left_participants.jsonl',
                'value': observed['observed_turn_heading_change_rad'],
                'sample_window_s': [0, (observed['frames'] - 1) / 20]}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior opposing-left analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
