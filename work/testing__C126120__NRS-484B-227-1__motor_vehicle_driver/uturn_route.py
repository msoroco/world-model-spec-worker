"""Source-shaped U-turn routes through one physically clear median opening.

Each segment has explicit forward or reverse gear. Geometry is a CPU design
check; Native motion and public-authority establishment need original sources.
"""

import math

from shapely.geometry import LineString, Point, Polygon


def _polygon(points, name):
    value = Polygon(points)
    if not value.is_valid or value.area <= 0:
        raise ValueError('Invalid ' + name)
    return value


def validate_plan(context, segments, barrier_footprints, *, body_radius_m):
    if not 0 < body_radius_m < 5 or not segments or len(segments) not in (1, 3):
        raise ValueError('One forward or forward-reverse-forward route required')
    gears = [segment.get('gear') for segment in segments]
    if gears not in (['forward'], ['forward', 'reverse', 'forward']):
        raise ValueError('U-turn gear sequence changed')
    right = _polygon(context['right_hand_roadway_xy_m'], 'right-hand roadway')
    destination = _polygon(context['destination_roadway_xy_m'], 'destination roadway')
    divider = _polygon(context['dividing_space_xy_m'], 'divider')
    opening = _polygon(context['opening_xy_m'], 'opening')
    if not divider.covers(opening) or len(barrier_footprints) != 2:
        raise ValueError('Two barrier sections and an internal opening required')
    barriers = [_polygon(points, 'physical barrier') for points in barrier_footprints]
    if any(barrier.intersects(opening) for barrier in barriers):
        raise ValueError('Barrier closes the opening')
    lines = []
    for index, segment in enumerate(segments):
        points = segment.get('waypoints_xy_m')
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError('Every movement needs route waypoints')
        line = LineString(points)
        if not line.is_simple or line.length <= 0:
            raise ValueError('Invalid movement path')
        if index and math.dist(segments[index - 1]['waypoints_xy_m'][-1], points[0]) > 1e-6:
            raise ValueError('U-turn movement phases do not join')
        swept = line.buffer(body_radius_m, cap_style=2, join_style=2)
        if swept.intersection(divider.difference(opening)).area > 1e-7:
            raise ValueError('Complete body crosses divider outside opening')
        if any(swept.intersects(barrier) for barrier in barriers):
            raise ValueError('Route collides with physical barrier')
        lines.append(line)
    first = segments[0]['waypoints_xy_m'][0]
    last = segments[-1]['waypoints_xy_m'][-1]
    if not right.covers(Point(first)) or not destination.covers(Point(last)):
        raise ValueError('Route does not join assigned divided-road carriageways')
    if not any(line.intersects(opening) for line in lines):
        raise ValueError('U-turn misses physical opening')
    a, b = segments[0]['waypoints_xy_m'][:2]
    c, d = segments[-1]['waypoints_xy_m'][-2:]
    incoming = (b[0] - a[0], b[1] - a[1])
    outgoing = (d[0] - c[0], d[1] - c[1])
    angle = math.degrees(math.atan2(incoming[0] * outgoing[1] - incoming[1] * outgoing[0],
                                    incoming[0] * outgoing[0] + incoming[1] * outgoing[1]))
    if abs(angle) < 150:
        raise ValueError('Final direction is not a U-turn')
    return {'gear_sequence': gears, 'route_length_m': sum(line.length for line in lines),
            'body_radius_m': body_radius_m, 'opening_traversed': True,
            'blocked_space_clearance': True, 'turn_angle_degrees': angle,
            'public_authority_judgment': 'unresolved', 'legal_conclusion': 'unresolved'}


class SegmentedController:
    """Apply a bounded Native control for each declared movement phase."""

    def __init__(self, segments, *, arrival_radius_m=0.8):
        if not segments or arrival_radius_m <= 0:
            raise ValueError('Missing movement controller segments')
        self.segments = segments
        self.arrival_radius_m = arrival_radius_m
        self.phase = 0
        self.waypoint = 1

    def step(self, vehicle):
        import carla
        transform = vehicle.get_transform()
        position = (float(transform.location.x), float(transform.location.y))
        current = self.segments[self.phase]
        points = current['waypoints_xy_m']
        while self.waypoint < len(points) - 1 and math.dist(position, points[self.waypoint]) <= self.arrival_radius_m:
            self.waypoint += 1
        target = points[self.waypoint]
        if math.dist(position, target) <= self.arrival_radius_m and self.waypoint == len(points) - 1:
            if self.phase == len(self.segments) - 1:
                control = carla.VehicleControl(throttle=0.0, brake=1.0)
                vehicle.apply_control(control)
                return {'completed': True, 'phase': self.phase, 'gear': current['gear']}
            self.phase += 1
            self.waypoint = 1
            current = self.segments[self.phase]
            target = current['waypoints_xy_m'][self.waypoint]
        reverse = current['gear'] == 'reverse'
        desired = math.atan2(target[1] - position[1], target[0] - position[0]) + (math.pi if reverse else 0)
        yaw = math.radians(float(transform.rotation.yaw))
        error = math.atan2(math.sin(desired - yaw), math.cos(desired - yaw))
        control = carla.VehicleControl(throttle=0.18 if reverse else 0.25,
                                       steer=max(-0.65, min(0.65, error)), reverse=reverse)
        vehicle.apply_control(control)
        return {'completed': False, 'phase': self.phase, 'gear': current['gear'],
                'steer': control.steer, 'reverse': reverse}
