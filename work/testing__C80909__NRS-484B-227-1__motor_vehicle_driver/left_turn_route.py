"""Build and follow a source-shaped 90-degree route through a divider opening.

The waypoint check proves planar clearance for the authored vehicle footprint.
Actual Native motion, barrier contact and public authority require local review.
"""

import math

from shapely.geometry import LineString, Point, Polygon


def _polygon(points, label):
    shape = Polygon(points)
    if not shape.is_valid or shape.area <= 0:
        raise ValueError('Invalid ' + label)
    return shape


def validate_route(context, points, *, body_radius_m):
    """Return a clearance receipt for an ordered right-roadway to left-turn path."""
    if len(points) < 4 or not 0 < body_radius_m < 10:
        raise ValueError('Route needs four points and a positive body radius')
    path = LineString(points)
    if not path.is_simple or path.length <= 0:
        raise ValueError('Route self-intersects or has zero length')
    right = _polygon(context['right_hand_roadway_xy_m'], 'right-hand roadway')
    destination = _polygon(context['destination_roadway_xy_m'], 'destination roadway')
    divider = _polygon(context['dividing_space_xy_m'], 'dividing space')
    opening = _polygon(context['opening_xy_m'], 'opening')
    if not divider.covers(opening):
        raise ValueError('Opening is outside dividing space')
    if not right.covers(Point(points[0])) or not destination.covers(Point(points[-1])):
        raise ValueError('Route does not join the assigned roadways')
    swept = path.buffer(body_radius_m, cap_style=2, join_style=2)
    if swept.intersection(divider.difference(opening)).area > 1e-7:
        raise ValueError('Complete-body route crosses blocked dividing space')
    if not swept.intersects(opening):
        raise ValueError('Route does not traverse physical opening')
    first = (points[1][0] - points[0][0], points[1][1] - points[0][1])
    last = (points[-1][0] - points[-2][0], points[-1][1] - points[-2][1])
    angle = math.degrees(math.atan2(first[0]*last[1]-first[1]*last[0],
                                    first[0]*last[0]+first[1]*last[1]))
    if not 60 <= angle <= 120:
        raise ValueError('Selected maneuver is not a 90-degree left turn')
    return {'route_length_m': path.length, 'body_radius_m': body_radius_m,
            'opening_traversed': True, 'blocked_space_clearance': True,
            'turn_angle_degrees': angle, 'legal_conclusion': 'unresolved'}


class WaypointController:
    """Apply bounded steer/throttle to a Native vehicle using route waypoints."""

    def __init__(self, points, *, arrival_radius_m=1.25):
        if len(points) < 2 or arrival_radius_m <= 0:
            raise ValueError('Incomplete waypoint controller')
        self.points = tuple((float(x), float(y)) for x, y in points)
        self.arrival_radius_m = arrival_radius_m
        self.index = 1

    def step(self, vehicle):
        location = vehicle.get_transform().location
        position = (float(location.x), float(location.y))
        while self.index < len(self.points)-1 and math.dist(position, self.points[self.index]) <= self.arrival_radius_m:
            self.index += 1
        target = self.points[self.index]
        yaw = math.radians(float(vehicle.get_transform().rotation.yaw))
        desired = math.atan2(target[1]-position[1], target[0]-position[0])
        error = math.atan2(math.sin(desired-yaw), math.cos(desired-yaw))
        arrived = self.index == len(self.points)-1 and math.dist(position, target) <= self.arrival_radius_m
        import carla
        control = carla.VehicleControl(throttle=0.0 if arrived else 0.27,
                                       steer=max(-0.7, min(0.7, error)),
                                       brake=1.0 if arrived else 0.0)
        vehicle.apply_control(control)
        return {'waypoint_index': self.index, 'arrived': arrived,
                'steer': control.steer, 'throttle': control.throttle}


def validate_blocked_space_route(context, points, barrier_footprints, *, body_radius_m):
    """Plan a diagnostic crossing of divider space outside the named opening.

    A path into a physical barrier is rejected. This geometry does not decide
    whether an unbarriered corridor is a statutory opening; source review must.
    """
    if len(points) < 4 or not 0 < body_radius_m < 10:
        raise ValueError('Complete blocked-space route and body radius required')
    path = LineString(points)
    if not path.is_simple or path.length <= 0:
        raise ValueError('Invalid blocked-space route')
    right = _polygon(context['right_hand_roadway_xy_m'], 'right-hand roadway')
    destination = _polygon(context['destination_roadway_xy_m'], 'destination roadway')
    divider = _polygon(context['dividing_space_xy_m'], 'dividing space')
    opening = _polygon(context['opening_xy_m'], 'opening')
    if not right.covers(Point(points[0])) or not destination.covers(Point(points[-1])):
        raise ValueError('Blocked-space route does not join roadways')
    swept = path.buffer(body_radius_m, cap_style=2, join_style=2)
    if swept.intersection(opening).area > 1e-7:
        raise ValueError('Blocked-space route enters named opening')
    if swept.intersection(divider.difference(opening)).area <= 1e-7:
        raise ValueError('Route does not cross named blocked dividing space')
    if not barrier_footprints:
        raise ValueError('Realized physical barrier footprints required')
    for footprint in barrier_footprints:
        if swept.intersects(_polygon(footprint, 'realized barrier')):
            raise ValueError('Route collides with physical barrier')
    first = (points[1][0]-points[0][0], points[1][1]-points[0][1])
    last = (points[-1][0]-points[-2][0], points[-1][1]-points[-2][1])
    angle = math.degrees(math.atan2(first[0]*last[1]-first[1]*last[0],
                                    first[0]*last[0]+first[1]*last[1]))
    if not 60 <= angle <= 120:
        raise ValueError('Blocked-space comparison needs a left turn')
    return {'route_length_m': path.length, 'body_radius_m': body_radius_m,
            'named_opening_traversed': False, 'divider_outside_opening_traversed': True,
            'realized_barrier_clearance': True, 'turn_angle_degrees': angle,
            'statutory_opening_judgment': 'unresolved', 'legal_conclusion': 'unresolved'}


def validate_right_roadway_continuation(context, points, *, body_radius_m):
    """Plan the fixed-site no-turn comparator wholly on the right-hand roadway."""
    if len(points) < 2 or not 0 < body_radius_m < 10:
        raise ValueError('Continuation route and body radius required')
    path = LineString(points)
    if not path.is_simple or path.length <= 0:
        raise ValueError('Invalid continuation route')
    right = _polygon(context['right_hand_roadway_xy_m'], 'right-hand roadway')
    swept = path.buffer(body_radius_m, cap_style=2, join_style=2)
    if not right.covers(swept):
        raise ValueError('Complete-body continuation leaves right-hand roadway')
    first = (points[1][0]-points[0][0], points[1][1]-points[0][1])
    last = (points[-1][0]-points[-2][0], points[-1][1]-points[-2][1])
    angle = math.degrees(math.atan2(first[0]*last[1]-first[1]*last[0],
                                    first[0]*last[0]+first[1]*last[1]))
    if abs(angle) > 15:
        raise ValueError('Continuation comparator turns')
    return {'route_length_m': path.length, 'body_radius_m': body_radius_m,
            'right_roadway_swept_clearance': True, 'turn_angle_degrees': angle,
            'legal_conclusion': 'unresolved'}


def validate_crossover_route(context, points, crossover_xy_m, *, body_radius_m):
    """Require an opening route through the sourced crossover footprint.

    The separate administrative establishment source is checked by the runner;
    this geometry alone cannot establish its public-authority status.
    """
    opening = validate_route(context, points, body_radius_m=body_radius_m)
    crossover = _polygon(crossover_xy_m, 'crossover')
    swept = LineString(points).buffer(body_radius_m, cap_style=2, join_style=2)
    if swept.intersection(crossover).area <= 1e-7:
        raise ValueError('Route misses sourced crossover footprint')
    return {**opening, 'crossover_footprint_traversed': True,
            'public_authority_establishment_judgment': 'unresolved'}
