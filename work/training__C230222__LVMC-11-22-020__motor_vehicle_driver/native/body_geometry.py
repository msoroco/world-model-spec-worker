"""Original Native body footprints and pairwise planar clearances.

The caller supplies actor transforms and bounding boxes from the same Native
frame. A zero planar separation is an overlap cue, not a collision verdict.
"""
import math


def require_finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Nonfinite Native body geometry')
    return float(value)


def footprint(actor):
    box = actor.bounding_box
    ext = box.extent
    if require_finite(ext.x) <= 0 or require_finite(ext.y) <= 0:
        raise ValueError('Native body box has no planar extent')
    pose = actor.get_transform()
    points = []
    for x, y in ((-ext.x, -ext.y), (ext.x, -ext.y),
                 (ext.x, ext.y), (-ext.x, ext.y)):
        local = type(box.location)(x=box.location.x + x,
                                   y=box.location.y + y,
                                   z=box.location.z)
        point = pose.transform(local)
        points.append([require_finite(point.x), require_finite(point.y)])
    return points


def _axes(polygon):
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            raise ValueError('Degenerate Native body footprint')
        yield (-dy / length, dx / length)


def _overlap(left, right):
    for ax, ay in list(_axes(left)) + list(_axes(right)):
        a = [x * ax + y * ay for x, y in left]
        b = [x * ax + y * ay for x, y in right]
        if max(a) < min(b) or max(b) < min(a):
            return False
    return True


def _point_segment_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if length2 <= 0:
        raise ValueError('Degenerate Native body edge')
    t = max(0.0, min(1.0, ((point[0] - start[0]) * dx +
                            (point[1] - start[1]) * dy) / length2))
    return math.hypot(point[0] - start[0] - t * dx,
                      point[1] - start[1] - t * dy)


def planar_gap(left, right):
    if type(left) is not list or type(right) is not list or len(left) != 4 or len(right) != 4:
        raise ValueError('Four original Native body corners required')
    for polygon in (left, right):
        for point in polygon:
            if len(point) != 2:
                raise ValueError('Invalid Native body corner')
            for value in point:
                require_finite(value)
    if _overlap(left, right):
        return 0.0
    return min(_point_segment_distance(point, a, b)
               for polygon, opposite in ((left, right), (right, left))
               for point in polygon
               for a, b in zip(opposite, opposite[1:] + opposite[:1]))


def scene_clearance(ego, participants):
    own = footprint(ego)
    bodies = []
    for actor in participants:
        if actor.id == ego.id:
            continue
        if not (actor.type_id.startswith('vehicle.') or
                actor.type_id.startswith('walker.')):
            continue
        points = footprint(actor)
        bodies.append({'actor_id': int(actor.id), 'type_id': actor.type_id,
                       'footprint_xy_m': points,
                       'planar_gap_m': planar_gap(own, points)})
    bodies.sort(key=lambda item: item['actor_id'])
    return {'ego_footprint_xy_m': own, 'participants': bodies,
            'minimum_surface_gap_m': min((item['planar_gap_m'] for item in bodies),
                                         default=None),
            'gap_method': 'original_native_2d_body_footprint_separation',
            'limitation': 'Planar body gap is not a three-dimensional contact or legal judgment.'}
