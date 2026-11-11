"""Native junction geometry and measured control inputs for the left-turn runner."""
import math
from shapely.geometry import MultiPoint, Polygon
from capture_sources import actor_sample


def _xy(location):
    return [float(location.x), float(location.y)]


def _direction(a, b):
    delta = [b[i]-a[i] for i in (0, 1)]
    length = math.hypot(*delta)
    if not math.isfinite(length) or length < 1e-6:
        raise ValueError('Native approach direction missing')
    return [value/length for value in delta]


def junction_context(selected):
    """Use the actual Native junction bounding box as an approximate polygon.

    The bbox is an engineering geometry envelope. Physical conflict regions and
    legal intersection boundaries still need local original-source review.
    """
    junction = selected['ego']['entry'].get_junction()
    if junction.id != selected['junction_id']:
        raise ValueError('Selected Native junction identity changed')
    box = junction.bounding_box
    center = _xy(box.location)
    extent = (float(box.extent.x), float(box.extent.y))
    yaw = math.radians(float(box.rotation.yaw))
    if any(not math.isfinite(value) or value <= 0 for value in extent) or not math.isfinite(yaw):
        raise ValueError('Invalid Native junction bounds')
    cosine, sine = math.cos(yaw), math.sin(yaw)
    polygon = [[center[0]+cosine*dx-sine*dy, center[1]+sine*dx+cosine*dy]
               for dx,dy in [(-extent[0],-extent[1]),(extent[0],-extent[1]),
                             (extent[0],extent[1]),(-extent[0],extent[1])]]
    outside = _xy(selected['oncoming']['outside'].transform.location)
    entry = _xy(selected['oncoming']['entry'].transform.location)
    direction = _direction(outside,entry)
    return {'native_junction_id':junction.id,
            'intersection_polygon_xy_m':polygon,
            'conflict_point_xy_m':center,
            'oncoming_direction_xy':direction,
            'ego_intended_maneuver':'left_turn',
            'geometry_source':'original Native junction bounding box and selected opposing waypoint chain',
            'boundary_limit':'Bounding-box envelope is not a legal intersection determination.'}


def control_inputs(selected, ego, oncoming, context, *, seen_oncoming_inside=False,
                   seen_ego_inside=False):
    """Read both original actor states before each control step."""
    ego_state, other_state = actor_sample(ego), actor_sample(oncoming)
    polygon = Polygon(context['intersection_polygon_xy_m'])
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError('Invalid Native junction envelope')
    ego_inside = MultiPoint(ego_state['body_vertices_xy_m']).convex_hull.intersects(polygon)
    other_inside = MultiPoint(other_state['body_vertices_xy_m']).convex_hull.intersects(polygon)
    ego_entry = _xy(selected['ego']['entry'].transform.location)
    ego_outside = _xy(selected['ego']['outside'].transform.location)
    ego_forward = _direction(ego_outside,ego_entry)
    ego_to_entry = [ego_entry[i]-ego_state['position_xy_m'][i] for i in (0,1)]
    distance_to_hold = sum(ego_to_entry[i]*ego_forward[i] for i in (0,1))
    direction = context['oncoming_direction_xy']
    other_to_conflict = [context['conflict_point_xy_m'][i]-other_state['position_xy_m'][i]
                         for i in (0,1)]
    remaining = sum(other_to_conflict[i]*direction[i] for i in (0,1))
    closing = sum(other_state['velocity_xy_mps'][i]*direction[i] for i in (0,1))
    seen_oncoming_inside |= other_inside
    seen_ego_inside |= ego_inside
    return {'distance_to_hold_m':distance_to_hold,
            'ego_speed_mps':math.hypot(*ego_state['velocity_xy_mps']),
            'oncoming_distance_to_conflict_m':remaining,
            'oncoming_closing_speed_mps':closing,
            'oncoming_in_intersection':other_inside,
            'oncoming_cleared':seen_oncoming_inside and not other_inside and remaining < 0,
            'turn_complete':seen_ego_inside and not ego_inside and distance_to_hold < 0,
            'seen_oncoming_inside':seen_oncoming_inside,
            'seen_ego_inside':seen_ego_inside}
