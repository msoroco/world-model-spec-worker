"""Source-bound reverse-route and moving-traffic conflict geometry.

This is a construction preflight, not a finding of statutory right of way.
The reviewed OpenDRIVE packet must identify both connected vehicle routes.
"""
from math import hypot, isfinite

from backing_geometry import _distance_to_segment, _point, _segment_gap


def validate(packet):
    required = ('map_sha256', 'map_name', 'junction_id', 'vehicle_blueprint_id',
                'traffic_blueprint_id', 'vehicle_reverse_route', 'traffic_route',
                'vehicle_half_width_m', 'traffic_half_width_m', 'control_source')
    if any(key not in packet for key in required):
        raise ValueError('reviewed original moving-traffic packet incomplete')
    if (len(packet['map_sha256']) != 64 or not packet['map_name'] or
            packet['junction_id'] is None or not packet['control_source']):
        raise ValueError('source-hashed original traffic junction required')
    if (not packet['vehicle_blueprint_id'].startswith('vehicle.') or
            not packet['traffic_blueprint_id'].startswith('vehicle.')):
        raise ValueError('two original vehicle blueprints required')
    reverse = packet['vehicle_reverse_route']
    traffic = packet['traffic_route']
    if len(reverse) < 2 or len(traffic) < 2:
        raise ValueError('two connected original vehicle routes required')
    if any(point.get('junction_id') != packet['junction_id'] for point in reverse + traffic):
        raise ValueError('original traffic routes must share reviewed junction')
    reverse_xy = [_point(point) for point in reverse]
    traffic_xy = [_point(point) for point in traffic]
    for route in (reverse_xy, traffic_xy):
        if any(hypot(b[0]-a[0], b[1]-a[1]) < .1 for a, b in zip(route, route[1:])):
            raise ValueError('original traffic route has degenerate segment')
    reverse_width = float(packet['vehicle_half_width_m'])
    traffic_width = float(packet['traffic_half_width_m'])
    if not all(isfinite(value) and value > 0 for value in (reverse_width, traffic_width)):
        raise ValueError('positive original traffic actor extents required')
    gap = min(_segment_gap(a,b,c,d) for a,b in zip(reverse_xy,reverse_xy[1:])
              for c,d in zip(traffic_xy,traffic_xy[1:]))
    if gap > reverse_width + traffic_width:
        raise ValueError('moving-traffic route misses reverse body corridor')
    return {'map_sha256': packet['map_sha256'], 'junction_id': packet['junction_id'],
            'route_gap_m': gap, 'route_conflict': True,
            'physical_realization': 'pending original Native execution'}


def traffic_in_reverse_corridor(packet, traffic_xy):
    validate(packet)
    if (not isinstance(traffic_xy, (list, tuple)) or len(traffic_xy) != 2 or
            any(type(value) not in (int, float) or not isfinite(value)
                for value in traffic_xy)):
        raise ValueError('finite original traffic vehicle position required')
    route = [_point(point) for point in packet['vehicle_reverse_route']]
    gap = min(_distance_to_segment(tuple(traffic_xy), a, b) for a,b in zip(route,route[1:]))
    extent = float(packet['vehicle_half_width_m']) + float(packet['traffic_half_width_m'])
    return {'in_corridor': gap <= extent, 'distance_to_reverse_route_m': gap,
            'corridor_extent_m': extent,
            'basis': 'original_map_reverse_route_and_original_moving_vehicle_position'}
