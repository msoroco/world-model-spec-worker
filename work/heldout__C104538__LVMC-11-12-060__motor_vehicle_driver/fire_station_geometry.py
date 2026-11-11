"""Source-bound fire-station entrance geometry for Native construction.

The caller must identify a real fire-station asset and the public-road/driveway
lane pair in the local map survey. This module rejects a merely labelled U-turn.
It does not establish that the surveyed asset is a fire station.
"""

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def _point(location):
    return Point(float(location.x), float(location.y))


def _heading(a, b):
    return atan2(b.y - a.y, b.x - a.x)


def _wrap(angle):
    return atan2(sin(angle), cos(angle))


def _lane_identity(waypoint):
    return (waypoint.road_id, waypoint.lane_id)


def _rectangle(a, b, half_width):
    dx, dy = b.x-a.x, b.y-a.y
    length = hypot(dx, dy)
    if length == 0: raise ValueError('zero-length mapped station segment')
    nx, ny = -dy/length*half_width, dx/length*half_width
    return [[a.x+nx, a.y+ny], [b.x+nx, b.y+ny],
            [b.x-nx, b.y-ny], [a.x-nx, a.y-ny]]


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside


def _hull(points):
    points = sorted(set((float(x),float(y)) for x,y in points))
    if len(points)<3:raise ValueError('body footprint lacks three distinct vertices')
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[];upper=[]
    for point in points:
        while len(lower)>=2 and cross(lower[-2],lower[-1],point)<=0:lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper)>=2 and cross(upper[-2],upper[-1],point)<=0:upper.pop()
        upper.append(point)
    return lower[:-1]+upper[:-1]


def _edges_cross(a,b,c,d):
    def orient(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return orient(a,b,c)*orient(a,b,d)<0 and orient(c,d,a)*orient(c,d,b)<0


def _overlap(body, polygon):
    body = _hull(body)
    return (any(_inside(v, polygon) for v in body) or
            any(_inside(v, body) for v in polygon) or
            any(_edges_cross(a,b,c,d) for a,b in zip(body,body[1:]+body[:1])
                for c,d in zip(polygon,polygon[1:]+polygon[:1])))


def validate_entrance(public_before, public_at, public_after, driveway_at, *,
                      source, min_branch_angle_deg=35):
    """Validate measured map geometry; return a reproducible local reference.

    All waypoints are original map waypoints chosen by a survey, not inferred
    from legal labels. A driveway must be a distinct lane diverging from the
    public lane near its entrance. The source binds a map landmark or survey.
    """
    if not isinstance(source, dict) or source.get('kind') not in ('map_landmark', 'operator_survey', 'authored_diagnostic'):
        raise ValueError('source-bound fire-station identification required')
    if not source.get('asset_id') or not source.get('source_sha256'):
        raise ValueError('fire-station source asset and hash required')
    if len(source['source_sha256']) != 64:
        raise ValueError('fire-station source SHA256 malformed')
    if _lane_identity(public_before) != _lane_identity(public_at) or _lane_identity(public_after) != _lane_identity(public_at):
        raise ValueError('public approach is not one continuous lane')
    if _lane_identity(driveway_at) == _lane_identity(public_at):
        raise ValueError('driveway is not a separate lane')
    before = _point(public_before.transform.location)
    at = _point(public_at.transform.location)
    after = _point(public_after.transform.location)
    driveway = _point(driveway_at.transform.location)
    if not 2.0 <= hypot(after.x - before.x, after.y - before.y) <= 40.0:
        raise ValueError('public approach sample spacing invalid')
    if hypot(driveway.x - at.x, driveway.y - at.y) > 12.0:
        raise ValueError('driveway is too far from public entrance')
    public_heading = _heading(before, after)
    driveway_heading = _heading(at, driveway)
    branch_angle = abs(_wrap(driveway_heading - public_heading)) * 180 / pi
    if branch_angle < min_branch_angle_deg:
        raise ValueError('driveway lacks a physical branch angle')
    return {
        'source': dict(source),
        'public_lane': _lane_identity(public_at),
        'driveway_lane': _lane_identity(driveway_at),
        'entrance_xy_m': [at.x, at.y],
        'public_heading_rad': public_heading,
        'driveway_heading_rad': driveway_heading,
        'branch_angle_deg': branch_angle,
        'entrance_polygon_xy': _rectangle(at, driveway, max(1.5, float(driveway_at.lane_width)/2)),
        'approach_polygon_xy': _rectangle(before, at, max(1.5, float(public_at.lane_width)/2)),
    }


def classify_path(samples, geometry, *, entrance_radius_m=5.0):
    """Describe realized center path without assigning a legal conclusion.

    Samples contain original-frame position and heading. A reversal requires
    observed motion on both sides of the episode; a driveway visit requires
    a measured position on its distinct mapped lane.
    """
    if len(samples) < 3:
        raise ValueError('original path has fewer than three samples')
    frames = [s['frame'] for s in samples]
    if frames != sorted(set(frames)):
        raise ValueError('original frame identities are not unique and increasing')
    x0, y0 = geometry['entrance_xy_m']
    near = [s['frame'] for s in samples if hypot(s['x_m'] - x0, s['y_m'] - y0) <= entrance_radius_m]
    driveway = [s['frame'] for s in samples if tuple(s['lane_id']) == tuple(geometry['driveway_lane'])]
    body_entrance = [s['frame'] for s in samples if s.get('body_vertices_xy') and
                     _overlap(s['body_vertices_xy'], geometry['entrance_polygon_xy'])]
    body_approach = [s['frame'] for s in samples if s.get('body_vertices_xy') and
                     _overlap(s['body_vertices_xy'], geometry['approach_polygon_xy'])]
    delta = abs(_wrap(samples[-1]['heading_rad'] - samples[0]['heading_rad'])) * 180 / pi
    return {
        'heading_change_deg': delta,
        'reversal_observed': delta >= 150.0,
        'near_entrance_frames': near,
        'driveway_frames': driveway,
        'body_entrance_overlap_frames': body_entrance,
        'body_approach_overlap_frames': body_approach,
        'entered_driveway': bool(driveway),
        'in_front_of_entrance_observed': bool(near),
        'purpose_of_turning': 'unresolved_contextual_judgment',
        'physical_fire_station_identity': 'unresolved_until_source_review',
    }
