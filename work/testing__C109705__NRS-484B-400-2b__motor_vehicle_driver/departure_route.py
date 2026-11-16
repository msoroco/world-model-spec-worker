"""Plan the paired Native-lane left-turn exits from one reviewed junction packet."""
import math

from shapely.geometry import LineString, Point, Polygon

from site_review import validate as review_site


def _xy(value, label):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('Finite '+label+' required')
    return [float(v) for v in value]


def plan(world, packet, root, *, farther):
    review = review_site(packet, root, world)
    lane_inventory = review['native_lane_inventory']['native_lane_ids']
    for road, lane in (('approach_road_id', 'approach_lane_id'),
                       ('outgoing_road_id', 'outgoing_lane_id')):
        if type(packet.get(lane)) is not int or packet[lane] not in lane_inventory[str(packet[road])]:
            raise ValueError('Selected Native turn lane absent: '+lane)
    name = 'far' if farther else 'near'
    route = packet.get('route_'+name+'_xy_m')
    if not isinstance(route, list) or len(route) < 4:
        raise ValueError('Complete '+name+' left-turn route required')
    points = [_xy(value, 'route point') for value in route]
    if any(math.dist(a,b) < 0.5 for a,b in zip(points,points[1:])):
        raise ValueError('Duplicate or undersampled turn route point')
    path = LineString(points)
    junction = Polygon(packet['junction_polygon_xy_m'])
    right = Polygon(packet['destination_right_half_polygon_xy_m'])
    center = LineString(packet['destination_centerline_xy_m'])
    start, end = Point(points[0]), Point(points[-1])
    if start.intersects(junction) or end.intersects(junction) or not path.intersects(junction):
        raise ValueError('Turn route must enter and leave sourced junction')
    entry = [points[1][i]-points[0][i] for i in (0,1)]
    departure = [points[-1][i]-points[-2][i] for i in (0,1)]
    cross = entry[0]*departure[1]-entry[1]*departure[0]
    if cross <= 0 or abs(sum(entry[i]*departure[i] for i in (0,1))) > .6*math.hypot(*entry)*math.hypot(*departure):
        raise ValueError('Authored route is not a left turn')
    footprint_radius = float(packet.get('exit_body_clearance_radius_m', 0))
    if not 0 < footprint_radius <= 2:
        raise ValueError('Finite complete-body exit envelope required')
    envelope = end.buffer(footprint_radius)
    if not right.covers(envelope) or envelope.intersects(center):
        raise ValueError('Complete exit body crosses destination centerline or right-half edge')
    clearance = center.distance(envelope)
    if farther:
        near = packet.get('route_near_xy_m')
        if not isinstance(near, list) or len(near) < 4:
            raise ValueError('Near paired route required')
        near_distance = center.distance(Point(_xy(near[-1], 'near exit')).buffer(footprint_radius))
        if clearance <= near_distance + .4:
            raise ValueError('Farther exit is not measurably farther from centerline')
    return {'route_xy_m': points, 'centerline_kind':review['centerline_kind'],
            'destination_exit_clearance_m':clearance,
            'source_review':review, 'physical_completion_claimed':False}
