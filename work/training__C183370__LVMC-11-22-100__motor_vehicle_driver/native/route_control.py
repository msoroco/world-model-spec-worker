"""Deterministic request controller for the two surveyed pavement routes."""
from math import atan2, degrees, hypot, sqrt


class RouteControl:
    def __init__(self, route_xy_m, *, speed_mps=4.0, reach_m=1.5,
                 steer_divisor_deg=40.0):
        if len(route_xy_m) < 2 or speed_mps <= 0 or reach_m <= 0 or steer_divisor_deg <= 0:
            raise ValueError('Route controller needs a positive route and speed')
        self.route = [tuple(point) for point in route_xy_m]
        self.speed_mps = speed_mps
        self.reach_m = reach_m
        self.steer_divisor_deg = steer_divisor_deg
        self.next_index = 1

    def decide(self, x, y, yaw_deg, observed_speed_mps):
        while (self.next_index < len(self.route)-1 and
               hypot(self.route[self.next_index][0]-x,
                     self.route[self.next_index][1]-y) <= self.reach_m):
            self.next_index += 1
        target = self.route[self.next_index]
        distance = hypot(target[0]-x, target[1]-y)
        finished = self.next_index == len(self.route)-1 and distance <= self.reach_m
        if finished:
            return {'throttle': 0.0, 'brake': 1.0, 'steer': 0.0,
                    'target_index': self.next_index, 'requested_route_complete': True}
        bearing = degrees(atan2(target[1]-y, target[0]-x))
        heading_error = (bearing-yaw_deg+180.0) % 360.0-180.0
        steer = max(-0.45, min(0.45, heading_error/self.steer_divisor_deg))
        desired = min(self.speed_mps, sqrt(4.0*max(0.0, distance-self.reach_m)))
        brake = 0.55 if observed_speed_mps > desired+0.3 else 0.0
        throttle = 0.0 if brake else 0.32 if observed_speed_mps < desired else 0.0
        return {'throttle': throttle, 'brake': brake, 'steer': steer,
                'target_index': self.next_index, 'requested_route_complete': False}
