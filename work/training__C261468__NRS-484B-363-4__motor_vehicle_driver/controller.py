"""Two-vehicle, same-direction overtaking controller for a surveyed school zone.

The command is a velocity request, not evidence that CARLA realized a pass.
The saved pose trace must establish the maneuver independently.
"""

import math


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _station(xyz, axis):
    return xyz[0] * axis[0] + xyz[1] * axis[1]


def _lateral(xyz, axis):
    return -xyz[0] * axis[1] + xyz[1] * axis[0]


class PassController:
    """Request a measured lateral departure, abreast interval and lane return."""

    def __init__(self, survey, *, pass_side=1, lane_width_m=3.5,
                 ego_speed_mps=8.0, other_speed_mps=4.0):
        axis = survey.get('road_axis_xy')
        bounds = survey.get('zone_station_bounds_m')
        if (not isinstance(axis, list) or len(axis) != 2 or
                not all(_number(v) for v in axis) or
                abs(math.hypot(*axis) - 1) > .01):
            raise ValueError('Controller needs surveyed unit route axis')
        if (not isinstance(bounds, list) or len(bounds) != 2 or
                not all(_number(v) for v in bounds) or bounds[0] >= bounds[1]):
            raise ValueError('Controller needs signed zone boundaries')
        if pass_side not in (-1, 1) or not 2.5 <= lane_width_m <= 4.5:
            raise ValueError('Controller needs surveyed pass-lane side and width')
        if not (0 < other_speed_mps < ego_speed_mps <= 15):
            raise ValueError('Controller speeds must produce a same-direction pass')
        ego = survey['ego']['xyz_m']
        other = survey['other']['xyz_m']
        if not (bounds[0] < _station(ego, axis) < _station(other, axis) < bounds[1]):
            raise ValueError('Vehicles must start behind and inside the zone')
        if abs(_lateral(ego, axis) - _lateral(other, axis)) > .75:
            raise ValueError('Vehicles must start in the same route lane')
        if (bounds[1] - _station(ego, axis)) < ego_speed_mps * 25:
            raise ValueError('Surveyed zone cannot contain a 25-second pass and return')
        self.axis = tuple(axis)
        self.bounds = tuple(bounds)
        self.start_lateral = _lateral(ego, axis)
        self.pass_lateral = self.start_lateral + pass_side * lane_width_m
        self.ego_speed = ego_speed_mps
        self.other_speed = other_speed_mps
        self.pass_side = pass_side
        self.phase = 'depart'

    def step(self, ego_xyz, other_xyz):
        """Return requested world velocities and phase from live actor poses."""
        if (not all(_number(v) for v in ego_xyz[:2]) or
                not all(_number(v) for v in other_xyz[:2])):
            raise ValueError('Live vehicle pose is missing')
        ego_s, other_s = _station(ego_xyz, self.axis), _station(other_xyz, self.axis)
        lateral = _lateral(ego_xyz, self.axis)
        if ego_s < self.bounds[0] or ego_s > self.bounds[1]:
            raise ValueError('Subject left the signed school zone')
        if self.phase == 'depart' and abs(lateral - self.pass_lateral) <= .35:
            self.phase = 'abreast'
        if self.phase == 'abreast' and ego_s - other_s >= 7:
            self.phase = 'return'
        if self.phase == 'return' and abs(lateral - self.start_lateral) <= .35:
            self.phase = 'complete'
        target = self.pass_lateral if self.phase in ('depart', 'abreast') else self.start_lateral
        lateral_speed = max(-1.5, min(1.5, (target - lateral) * 1.2))
        ax, ay = self.axis
        ego_v = (self.ego_speed * ax - lateral_speed * ay,
                 self.ego_speed * ay + lateral_speed * ax)
        other_v = (self.other_speed * ax, self.other_speed * ay)
        return {'phase': self.phase, 'ego_velocity_xy_mps': ego_v,
                'other_velocity_xy_mps': other_v,
                'ego_station_m': ego_s, 'other_station_m': other_s,
                'ego_lateral_m': lateral,
                'subject_behind': ego_s < other_s,
                'subject_ahead': ego_s > other_s,
                'in_signed_zone': self.bounds[0] <= ego_s <= self.bounds[1]}


def request_velocities(ego, other, carla, command):
    """Issue both velocity requests; caller records original poses after ticking."""
    ex, ey = command['ego_velocity_xy_mps']
    ox, oy = command['other_velocity_xy_mps']
    ego.set_target_velocity(carla.Vector3D(x=ex, y=ey, z=0))
    other.set_target_velocity(carla.Vector3D(x=ox, y=oy, z=0))
