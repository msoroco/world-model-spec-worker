"""Retain original-tick fire apparatus geometry and state for saved processing.

The caller supplies synchronized Native frame/time and explicit lamp/siren
readbacks. Alarm purpose and subject authorization remain separate context.
"""

from __future__ import annotations

import json
from math import atan2, hypot, isfinite
from pathlib import Path


def _xy(value):
    return float(value.x), float(value.y)


def ground_corners(actor):
    """Take the four lower vertices of the actor's current world bounding box."""
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8:
        raise ValueError("Native actor needs eight world bounding-box vertices")
    if any(not all(isfinite(float(getattr(vertex, axis))) for axis in ("x", "y", "z"))
           for vertex in vertices):
        raise ValueError("Native body vertices must be finite")
    lower = sorted(vertices, key=lambda vertex: float(vertex.z))[:4]
    points = [_xy(vertex) for vertex in lower]
    if len(set(points)) != 4:
        raise ValueError("Native ground footprint has duplicate corners")
    centre = (sum(point[0] for point in points) / 4,
              sum(point[1] for point in points) / 4)
    points.sort(key=lambda point: atan2(point[1] - centre[1], point[0] - centre[0]))
    area = abs(sum(points[i][0] * points[(i + 1) % 4][1] -
                   points[(i + 1) % 4][0] * points[i][1] for i in range(4))) / 2
    if area <= 1e-6:
        raise ValueError("Native ground footprint has no area")
    return [list(point) for point in points]


def _speed(actor):
    velocity = actor.get_velocity()
    values = (float(velocity.x), float(velocity.y), float(velocity.z))
    if not all(isfinite(value) for value in values):
        raise ValueError("Native actor velocity must be finite")
    return hypot(*values[:2])


class FireSourceRecorder:
    """Write synchronized original sources once; no post-hoc source repair."""

    def __init__(self, directory, ego, apparatus):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.ego, self.apparatus = ego, apparatus
        if not ego.id or not apparatus.id or ego.id == apparatus.id:
            raise ValueError("Fire participants need distinct Native actor IDs")
        self.participants = (directory / "participant_footprints.jsonl").open("x")
        try:
            self.states = (directory / "participant_state.jsonl").open("x")
        except BaseException:
            self.participants.close()
            raise
        self.previous_frame = None
        self.previous_time = None

    def append(self, frame, time_s, *, warning_lamp_readback, siren_readback):
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not isfinite(time_s) or
                (self.previous_frame is not None and
                 (frame != self.previous_frame + 1 or time_s <= self.previous_time))):
            raise ValueError("Original fire source frame/time is invalid or missing")
        if type(warning_lamp_readback) is not bool or type(siren_readback) is not bool:
            raise ValueError("Fire warning lamp and siren require explicit readbacks")
        ego_corners = ground_corners(self.ego)
        apparatus_corners = ground_corners(self.apparatus)
        ego_speed, apparatus_speed = _speed(self.ego), _speed(self.apparatus)
        ego_transform, apparatus_transform = self.ego.get_transform(), self.apparatus.get_transform()
        ego_forward, apparatus_forward = _xy(ego_transform.get_forward_vector()), _xy(apparatus_transform.get_forward_vector())
        ego_norm, apparatus_norm = hypot(*ego_forward), hypot(*apparatus_forward)
        if min(ego_norm, apparatus_norm) < 1e-9:
            raise ValueError("Native participant heading is unavailable")
        aligned = ((ego_forward[0] * apparatus_forward[0] +
                    ego_forward[1] * apparatus_forward[1]) / (ego_norm * apparatus_norm) > .98)
        ego_xy, apparatus_xy = _xy(ego_transform.location), _xy(apparatus_transform.location)
        ahead = ((apparatus_xy[0] - ego_xy[0]) * ego_forward[0] +
                 (apparatus_xy[1] - ego_xy[1]) * ego_forward[1]) > 0
        lateral = abs((apparatus_xy[0] - ego_xy[0]) * ego_forward[1] -
                      (apparatus_xy[1] - ego_xy[1]) * ego_forward[0]) / ego_norm
        moving_ego, moving_apparatus = ego_speed > .15, apparatus_speed > .15
        parked = not moving_ego and bool(self.ego.get_control().hand_brake)
        participant = {"frame": frame, "time_s": time_s, "ego_id": self.ego.id,
                       "apparatus_id": self.apparatus.id, "ego_corners": ego_corners,
                       "apparatus_corners": apparatus_corners}
        state = {"frame": frame, "time_s": time_s,
                 "apparatus_moving": moving_apparatus, "ego_moving": moving_ego,
                 "ego_following": moving_ego and moving_apparatus and aligned and ahead and lateral <= 2.5,
                 "ego_parked": parked, "warning_lamp": warning_lamp_readback,
                 "siren": siren_readback}
        self.participants.write(json.dumps(participant, allow_nan=False) + "\n")
        self.states.write(json.dumps(state, allow_nan=False) + "\n")
        self.participants.flush()
        self.states.flush()
        self.previous_frame, self.previous_time = frame, time_s
        return participant, state

    def close(self):
        self.participants.close()
        self.states.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
