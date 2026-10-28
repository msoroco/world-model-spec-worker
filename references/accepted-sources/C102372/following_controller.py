"""Prospective observed-state feedback for the unchanged C104496 crest.
No CARLA import, driving, legal threshold, or native feasibility claim.
The native caller must supply fresh synchronized actor state on every tick.
"""
import math
from dataclasses import dataclass

DT = 0.05
CREST = 750.0
ROUTE_LENGTH = 1500.0


def elevation(station):
    if station < 650.0:
        return -4.0 + 0.08 * (station - 650.0)
    if station > 850.0:
        return -4.0 - 0.08 * (station - 850.0)
    return -0.0004 * (station - CREST) ** 2


def grade(station):
    return 0.08 if station < 650.0 else -0.08 if station > 850.0 else -0.0008 * (station - CREST)


def _primitive(u):
    return 0.5 * (u * math.sqrt(1.0 + u * u) + math.asinh(u))


def route_distance(station):
    """3D centreline arc length from x=0; native x is OpenDRIVE station here."""
    if not 0.0 <= station <= ROUTE_LENGTH:
        raise ValueError('Body outside supported centreline; do not extrapolate')
    slope_scale = math.sqrt(1.0 + 0.08 ** 2)
    if station <= 650.0:
        return station * slope_scale
    crest_part = (_primitive(0.08) - _primitive(-0.0008 * (min(station, 850.0) - CREST))) / 0.0008
    return 650.0 * slope_scale + crest_part + max(0.0, station - 850.0) * slope_scale


def body_references(vertices):
    if len(vertices) != 8 or any(len(v) != 3 for v in vertices):
        raise ValueError('Require all eight actual native world-space box vertices')
    values = [route_distance(float(v[0])) for v in vertices]
    return {'rear_route_m': min(values), 'front_route_m': max(values),
            'convention': 'Extrema of all eight native body vertices projected by world x onto the unchanged straight 3D centreline; not native component gap'}


def along_route_body_gap(ego_vertices, leader_vertices):
    a, b = body_references(ego_vertices), body_references(leader_vertices)
    return b['rear_route_m'] - a['front_route_m']


def tangent_speed(position, velocity):
    g = grade(float(position[0]))
    return (float(velocity[0]) + g * float(velocity[2])) / math.sqrt(1.0 + g * g)


def leader_requested_speed(time_s):
    # Engineering profile for coverage only; all observed histories remain mandatory.
    if time_s < 2.0 or time_s >= 34.0:
        return 0.0
    if time_s < 22.0 or time_s >= 28.0:
        return 9.0
    return 6.0


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


@dataclass
class FollowingController:
    target_body_gap_m: float
    last_frame: int = -1
    integral_speed_error: float = 0.0

    def step(self, frame, time_s, ego, leader):
        """Consume actual pre-control states, never an authored leader trajectory.
        State keys: actor_id, body_vertices_m, position_m, velocity_mps.
        Returns requests and the complete inputs used, for same-episode retention.
        """
        if not 120.0 <= self.target_body_gap_m <= 180.0:
            raise ValueError('Unselected prospective physical gap')
        if frame <= self.last_frame or ego['actor_id'] == leader['actor_id']:
            raise ValueError('Require a fresh synchronized frame and distinct actors')
        if not math.isfinite(time_s):
            raise ValueError('Require native elapsed time')
        observed_gap = along_route_body_gap(ego['body_vertices_m'], leader['body_vertices_m'])
        ego_speed = tangent_speed(ego['position_m'], ego['velocity_mps'])
        leader_speed = tangent_speed(leader['position_m'], leader['velocity_mps'])
        gap_error = observed_gap - self.target_body_gap_m
        # Position and relative-speed feedback: stopping/changes emerge from leader state.
        requested_speed = _clamp(leader_speed + 0.65 * gap_error + 0.50 * (leader_speed - ego_speed), 0.0, 17.0)
        error = requested_speed - ego_speed
        trial = _clamp(self.integral_speed_error + DT * error, -5.0, 5.0)
        observed_leader_control = leader['applied_control']
        feedforward = float(observed_leader_control['throttle']) - float(observed_leader_control['brake'])
        output = feedforward + 0.6 * error + 0.15 * trial
        if not ((output >= 1.0 and error > 0.0) or (output <= -1.0 and error < 0.0)):
            self.integral_speed_error = trial
        output = feedforward + 0.6 * error + 0.15 * self.integral_speed_error
        self.last_frame = frame
        stopped_leader_closure = abs(leader_speed) < 0.1 and gap_error <= 0.3
        return {
            'throttle': 0.0 if stopped_leader_closure else _clamp(output, 0.0, 1.0), 'brake': 0.7 if stopped_leader_closure else _clamp(-output, 0.0, 1.0),
            'hand_brake': (stopped_leader_closure or requested_speed < 0.02) and abs(ego_speed) < 0.05,
            'requested_ego_speed_mps': requested_speed,
            'actual_controller_inputs': {'frame': frame, 'time_s': time_s,
                'ego_actor_id': ego['actor_id'], 'leader_actor_id': leader['actor_id'],
                'ego_state': ego, 'leader_state': leader,
                'observed_along_route_body_gap_m': observed_gap, 'target_body_gap_m': self.target_body_gap_m,
                'ego_tangent_speed_mps': ego_speed, 'leader_tangent_speed_mps': leader_speed,
                'relative_tangent_speed_mps': leader_speed - ego_speed,
                'observed_leader_control_feedforward':feedforward,
                'integral_speed_error': self.integral_speed_error},
            'limitations': 'Prospective longitudinal control only; native route steering, body clearance, grade response, braking and measurement support require independent native checks.'}
