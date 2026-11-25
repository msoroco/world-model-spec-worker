"""Author CPU diagnostic caravan spawn spacing from a sourced road direction.

This computes planned transforms. Native blueprint extents and motion remain
original-source checks after capture.
"""
import copy
import math

from shapely.geometry import Polygon


def plan(packet, spacing_m, *, member_half_length_m=1.0,
         entrant_half_length_m=1.0, drawn_half_length_m=1.0):
    if type(spacing_m) not in (int, float) or not math.isfinite(spacing_m) or spacing_m <= 0:
        raise ValueError('Finite positive member center spacing required')
    members = packet.get('caravan_vehicles', [])
    if len(members) != 3:
        raise ValueError('Three authored caravan members required')
    forward = packet.get('road_forward_xy', [])
    if len(forward) != 2 or any(type(x) not in (int, float) or not math.isfinite(x)
                                for x in forward):
        raise ValueError('Finite sourced road direction required')
    length = math.hypot(*forward)
    if length <= 0:
        raise ValueError('Nonzero sourced road direction required')
    unit = (forward[0] / length, forward[1] / length)
    road = Polygon(packet.get('roadway_polygon_xy_m', []))
    if not road.is_valid or road.area <= 0:
        raise ValueError('Valid sourced road polygon required')
    for half in (member_half_length_m, entrant_half_length_m, drawn_half_length_m):
        if type(half) not in (int, float) or not math.isfinite(half) or half <= 0:
            raise ValueError('Finite positive diagnostic body extent required')
    result = copy.deepcopy(packet)
    anchor = members[0]['transform']
    if any(type(anchor.get(key)) not in (int, float) or not math.isfinite(anchor[key])
           for key in ('x', 'y')):
        raise ValueError('Finite first reviewed transform required')
    ax, ay = float(anchor['x']), float(anchor['y'])
    for index, member in enumerate(result['caravan_vehicles']):
        x, y = ax + index * spacing_m * unit[0], ay + index * spacing_m * unit[1]
        member['transform']['x'], member['transform']['y'] = x, y
        corners = [(x + dx, y + dy) for dx in (-member_half_length_m, member_half_length_m)
                   for dy in (-member_half_length_m, member_half_length_m)]
        if not road.covers(Polygon((corners[0], corners[1], corners[3], corners[2]))):
            raise ValueError('Planned caravan body leaves sourced road')
    relative = result.get('drawn_unit', {}).get('relative_transform', {})
    offset = relative.get('x')
    if type(offset) not in (int, float) or not math.isfinite(offset) or offset >= 0:
        raise ValueError('Drawn unit needs a finite rearward relative offset')
    dx, dy = ax + offset * unit[0], ay + offset * unit[1]
    corners = [(dx + x, dy + y) for x in (-drawn_half_length_m, drawn_half_length_m)
               for y in (-drawn_half_length_m, drawn_half_length_m)]
    if not road.covers(Polygon((corners[0], corners[1], corners[3], corners[2]))):
        raise ValueError('Planned drawn body leaves sourced road')
    opening = spacing_m - 2 * member_half_length_m
    entrant_length = 2 * entrant_half_length_m
    result['entrant_route_outcome'] = 'occupy' if opening > entrant_length else 'stop_before'
    result['authored_member_center_spacing_m'] = float(spacing_m)
    return result, {'center_spacing_m': float(spacing_m),
                    'diagnostic_opening_m': opening,
                    'diagnostic_entrant_length_m': entrant_length,
                    'planned_outcome': result['entrant_route_outcome'],
                    'actual_native_geometry_verified': False,
                    'statutory_danger_judgment': 'unresolved'}
