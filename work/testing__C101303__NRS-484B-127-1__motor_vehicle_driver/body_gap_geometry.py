"""Turn an engineering complete-body gap into a measured center spacing.

No CARLA import is needed. Native actors supply their world body vertices when
this helper is integrated into a runner. The gap remains an engineering knob.
"""
import math


def _xy(value, label):
    if len(value) < 2:
        raise ValueError('Missing ' + label)
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(x) for x in point):
        raise ValueError('Nonfinite ' + label)
    return point


def projected_body_offset(ego_center, ego_vertices, lead_center, lead_vertices,
                          route_forward_xy):
    """Return ego front plus lead rear extents along the following route."""
    ex, ey = _xy(ego_center, 'ego center')
    lx, ly = _xy(lead_center, 'lead center')
    fx, fy = _xy(route_forward_xy, 'route forward')
    norm = math.hypot(fx, fy)
    if norm <= 0:
        raise ValueError('Zero following route direction')
    fx, fy = fx / norm, fy / norm
    if len(ego_vertices) < 4 or len(lead_vertices) < 4:
        raise ValueError('Complete body vertices required')
    ego_front = max((_xy(p, 'ego vertex')[0] - ex) * fx +
                    (_xy(p, 'ego vertex')[1] - ey) * fy for p in ego_vertices)
    lead_rear = -min((_xy(p, 'lead vertex')[0] - lx) * fx +
                     (_xy(p, 'lead vertex')[1] - ly) * fy for p in lead_vertices)
    if ego_front <= 0 or lead_rear <= 0:
        raise ValueError('Body extents do not bracket actor centers')
    return ego_front + lead_rear


def native_body_offset(ego, lead, route_forward_xy):
    """Read current Native bounding boxes and transforms without importing CARLA."""
    def actor_source(actor):
        center = actor.get_location()
        box = actor.bounding_box
        vertices = box.get_world_vertices(actor.get_transform())
        return (center.x, center.y), [(v.x, v.y) for v in vertices]
    ec, ev = actor_source(ego)
    lc, lv = actor_source(lead)
    return projected_body_offset(ec, ev, lc, lv, route_forward_xy)
