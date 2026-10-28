"""Prospective observed-body gap-centre approach and smooth native lane entry.

Engineering requests only. No legal sufficiency or danger predicate.
"""
from dataclasses import dataclass
import math
from caravan_controller_v3 import SpeedController, clamp


def entry_pair(location):
    if location == 'front':
        return 'ego', 'front'
    if location == 'rear':
        return 'rear', 'ego'
    raise ValueError('Unassessed entry location')


def lateral_request(time_s):
    if time_s <= 14:
        return 6., 0.
    if time_s >= 20:
        return 2., 0.
    u = (time_s-14)/6
    # Zero lateral velocity at both authored endpoints; physical response retained.
    return 6-4*(3*u*u-2*u*u*u), -4*(6*u-6*u*u)/6


def longitudinal_bounds(state):
    vertices = state['body_vertices_native_m']
    if len(vertices) != 8:
        raise ValueError('All native occupied body vertices required')
    return min(v[0] for v in vertices), max(v[0] for v in vertices)


@dataclass
class EntrantController:
    location: str
    cruise_mps: float = 6.
    duration_s: float = 30.
    last_frame: int = -1
    speed: SpeedController = None

    def __post_init__(self):
        entry_pair(self.location)
        if self.cruise_mps != 6 or self.duration_s != 30:
            raise ValueError('Prospective entry contract has not assessed this setting')
        self.speed = SpeedController()

    def step(self, frame, elapsed_s, group, outsider):
        if frame <= self.last_frame:
            raise ValueError('Fresh actual observed predecessor states required')
        follower, predecessor = entry_pair(self.location)
        ids = [group[follower]['actor_id'],group[predecessor]['actor_id'],outsider['actor_id']]
        if len(set(ids)) != 3:
            raise ValueError('Distinct group members and independent outsider required')
        behind_front = longitudinal_bounds(group[follower])[1]
        ahead_rear = longitudinal_bounds(group[predecessor])[0]
        lo, hi = longitudinal_bounds(outsider)
        centre = (behind_front+ahead_rear)/2
        error = centre-(lo+hi)/2
        base = (group[follower]['velocity_mps'][0]+group[predecessor]['velocity_mps'][0])/2
        target = 0. if elapsed_s < 2 or elapsed_s >= self.duration_s-8 else clamp(base+.5*error,0.,self.cruise_mps+3)
        request = self.speed.step(outsider['velocity_mps'][0],target,.12 if target else 0.)
        desired_y, desired_lateral_velocity = lateral_request(elapsed_s)
        desired_heading = math.atan2(desired_lateral_velocity,max(1.,outsider['speed_mps']))
        heading = math.radians(outsider['heading_deg'])
        heading_error = math.atan2(math.sin(desired_heading-heading),math.cos(desired_heading-heading))
        request['steer'] = clamp(-.35*(outsider['position_m'][1]-desired_y)+1.2*heading_error,-.5,.5)
        request['actual_controller_inputs'] = {'native_frame':frame,'elapsed_s':elapsed_s,'follower':group[follower],'predecessor':group[predecessor],'outsider':outsider,'observed_gap_midpoint_x_m':centre,'observed_outsider_body_midpoint_x_m':(lo+hi)/2,'desired_lane_y_m':desired_y,'requested_lateral_velocity_mps':desired_lateral_velocity,'desired_heading_rad':desired_heading,'entry_location':self.location}
        self.last_frame = frame
        return request
