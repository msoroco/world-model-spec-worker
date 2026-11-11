"""Read original opposing-left sources without making a legal judgment."""

import json
from hashlib import sha256
from math import atan2, cos, hypot, isfinite, sin
from pathlib import Path


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows:
        raise ValueError('Opposing-left source has no frames')
    return rows


def _center(corners):
    if len(corners) != 4 or any(len(point) != 2 or
            not all(isfinite(v) for v in point) for point in corners):
        raise ValueError('Opposing-left body needs four finite original corners')
    return [sum(point[axis] for point in corners) / 4 for axis in (0, 1)]


def _angle_change(first, last):
    return atan2(sin(last - first), cos(last - first))


def measure_opposing_left(root):
    root = Path(root)
    context_path, context_sha = _required(root, 'opposing_left_context.json')
    rows_path, rows_sha = _required(root, 'opposing_left_participants.jsonl')
    map_path, map_sha = _required(root, 'video_frames.jsonl')
    context = json.loads(context_path.read_text())
    rows, mapping = _rows(rows_path), _rows(map_path)
    if context.get('format') != 'worker-opposing-left-original-context' or len(rows) != len(mapping):
        raise ValueError('Opposing-left source/context length differs')
    turning_route, opposite_route = context['turning_route'], context['opposite_route']
    if not turning_route or not opposite_route or any(
            not route[0].get('heading_xy') for route in (turning_route, opposite_route)):
        raise ValueError('Opposing-left route context missing')
    a, b = turning_route[0]['heading_xy'], opposite_route[0]['heading_xy']
    exit_heading = turning_route[-1]['heading_xy']
    if a[0] * b[0] + a[1] * b[1] > -.8 or a[0] * exit_heading[1] - a[1] * exit_heading[0] < .5:
        raise ValueError('Opposing-left route context does not establish opposing leftward plan')
    turning_centers, opposite_centers, turn_headings = [], [], []
    previous = None
    for row, frame in zip(rows, mapping):
        if (row.get('frame'), row.get('time_s')) != (frame.get('carla_frame'), frame.get('time_s')):
            raise ValueError('Opposing-left original frame-map join failed')
        if previous is not None and (row['frame'] != previous[0] + 1 or
                abs(row['time_s'] - previous[1] - .05) > 1e-4):
            raise ValueError('Opposing-left original frames are not 20 Hz')
        if (row.get('turning_actor_id'), row.get('opposite_actor_id')) != (
                context.get('turning_actor_id'), context.get('opposite_actor_id')):
            raise ValueError('Opposing-left original participant identity changed')
        heading = row.get('turning_heading_rad')
        other_heading = row.get('opposite_heading_rad')
        if not isinstance(heading, (int, float)) or not isinstance(other_heading, (int, float)) or not (
                isfinite(heading) and isfinite(other_heading)):
            raise ValueError('Opposing-left original heading missing or nonfinite')
        turning_centers.append(_center(row['turning_corners']))
        opposite_centers.append(_center(row['opposite_corners']))
        turn_headings.append(heading)
        previous = row['frame'], row['time_s']
    observed_change = _angle_change(turn_headings[0], turn_headings[-1])
    start_separation = hypot(*(turning_centers[0][i] - opposite_centers[0][i] for i in (0, 1)))
    end_separation = hypot(*(turning_centers[-1][i] - opposite_centers[-1][i] for i in (0, 1)))
    return {'method': 'measure_opposing_left',
            'value': {'frames': len(rows), 'junction_id': context['junction_id'],
                      'turning_actor_id': context['turning_actor_id'],
                      'opposite_actor_id': context['opposite_actor_id'],
                      'planned_left_cross': a[0] * exit_heading[1] - a[1] * exit_heading[0],
                      'approach_heading_dot': a[0] * b[0] + a[1] * b[1],
                      'observed_turn_heading_change_rad': observed_change,
                      'start_body_center_separation_m': start_separation,
                      'end_body_center_separation_m': end_separation,
                      'turn_physically_completed': None,
                      'legal_exception_claimed': False},
            'sources': {'opposing_left_context.json': context_sha,
                        'opposing_left_participants.jsonl': rows_sha,
                        'video_frames.jsonl': map_sha}}
