"""Original Native route and participant source for the opposing-left branch.

The geometry and readbacks are observations. They do not establish that the
statutory opposite-direction exception applies to the eventual recording.
"""

import json
from math import atan2, hypot, isfinite
from pathlib import Path

from ending_road_source_capture import _body, _linked


def _heading(waypoint):
    direction = waypoint.transform.get_forward_vector()
    length = hypot(direction.x, direction.y)
    if not isfinite(length) or length < 1e-6:
        raise ValueError('Opposing-left route heading is unavailable')
    return [direction.x / length, direction.y / length]


def _route_source(path, junction_id):
    if len(path) < 3 or path[0].is_junction or path[-1].is_junction:
        raise ValueError('Opposing-left route needs exterior endpoints and junction')
    if any(not _linked(first, second) for first, second in zip(path, path[1:])):
        raise ValueError('Opposing-left route has disconnected Native successors')
    points = []
    entered = False
    for waypoint in path:
        local_junction = str(waypoint.get_junction().id) if waypoint.is_junction else None
        if local_junction is not None:
            entered = True
            if local_junction != junction_id:
                raise ValueError('Opposing-left routes enter different junctions')
        location = waypoint.transform.location
        values = (location.x, location.y)
        if not all(isfinite(v) for v in values):
            raise ValueError('Opposing-left route has nonfinite position')
        points.append({'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                       'junction_id': local_junction, 'xy': list(values),
                       'heading_xy': _heading(waypoint)})
    if not entered:
        raise ValueError('Opposing-left route misses selected junction')
    return points


def context_from_native(selection, turning_actor, opposite_actor):
    junction_id = str(selection['junction_id'])
    turning = _route_source(selection['turning'], junction_id)
    opposite = _route_source(selection['opposite'], junction_id)
    a, b = turning[0]['heading_xy'], opposite[0]['heading_xy']
    if a[0] * b[0] + a[1] * b[1] > -.8:
        raise ValueError('Original approaches are not opposing')
    exit_heading = turning[-1]['heading_xy']
    if a[0] * exit_heading[1] - a[1] * exit_heading[0] < .5:
        raise ValueError('Original selected exit is not leftward')
    return {'format': 'worker-opposing-left-original-context',
            'junction_id': junction_id, 'map_name': selection['map_name'],
            'turning_actor_id': str(turning_actor.id),
            'opposite_actor_id': str(opposite_actor.id),
            'turning_route': turning, 'opposite_route': opposite,
            'legal_exception_claimed': False}


class OpposingLeftSourceRecorder:
    def __init__(self, output, context, turning_actor, opposite_actor):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.context_path = self.output / 'opposing_left_context.json'
        self.rows_path = self.output / 'opposing_left_participants.jsonl'
        if self.context_path.exists() or self.rows_path.exists():
            raise FileExistsError('Retain prior opposing-left original source')
        if (context['turning_actor_id'], context['opposite_actor_id']) != (
                str(turning_actor.id), str(opposite_actor.id)):
            raise ValueError('Opposing-left Native participant identity differs')
        self.turning, self.opposite = turning_actor, opposite_actor
        self.context_path.write_text(json.dumps(context, indent=2, allow_nan=False) + '\n')
        self.stream = self.rows_path.open('x')
        self.previous = None

    def append(self, frame, time_s):
        if type(frame) is not int or not isfinite(time_s):
            raise ValueError('Opposing-left original frame/time invalid')
        if self.previous is not None and (frame != self.previous[0] + 1 or
                abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError('Opposing-left original source is not 20 Hz')
        row = {'frame': frame, 'time_s': time_s,
               'turning_actor_id': str(self.turning.id),
               'opposite_actor_id': str(self.opposite.id),
               'turning_corners': _body(self.turning),
               'opposite_corners': _body(self.opposite),
               'turning_heading_rad': self._actor_heading(self.turning),
               'opposite_heading_rad': self._actor_heading(self.opposite)}
        row['value'] = {'turning_corners': row['turning_corners'],
                        'opposite_corners': row['opposite_corners'],
                        'turning_heading_rad': row['turning_heading_rad'],
                        'opposite_heading_rad': row['opposite_heading_rad']}
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    @staticmethod
    def _actor_heading(actor):
        vector = actor.get_transform().get_forward_vector()
        if not all(isfinite(v) for v in (vector.x, vector.y)) or hypot(vector.x, vector.y) < 1e-6:
            raise ValueError('Opposing-left actor heading unavailable')
        return atan2(vector.y, vector.x)

    def close(self):
        self.stream.close()
