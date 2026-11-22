"""Original Native actor/body samples for the prohibited-turn comparison."""
import math

PHASES = {'mounted_approach', 'dismount_hold', 'afoot_reversal',
          'mounted_reversal', 'turn_complete'}


def body(actor):
    points = actor.bounding_box.get_world_vertices(actor.get_transform())
    vertices = [[float(p.x), float(p.y), float(p.z)] for p in points]
    if len(vertices) < 4 or any(not all(math.isfinite(v) for v in point)
                                for point in vertices):
        raise ValueError('original Native actor body geometry missing')
    return vertices


def sample(actors, *, frame, time_s, phase):
    if type(frame) is not int or frame < 0 or type(time_s) not in (int, float) or not math.isfinite(time_s):
        raise ValueError('original Native frame/time missing')
    if phase not in PHASES:
        raise ValueError('unknown constructed turn phase')
    sign, bike, operator = (actors[name] for name in ('sign', 'bicycle', 'operator'))
    if len({sign.id, bike.id, operator.id}) != 3:
        raise ValueError('sign, bicycle and operator must be distinct Native actors')
    return {'frame': frame, 'time_s': time_s, 'phase': phase,
            'operator_id': operator.id, 'bicycle_id': bike.id,
            'sign_id': sign.id,
            'operator_body_vertices_m': body(operator),
            'bicycle_body_vertices_m': body(bike),
            'sign_body_vertices_m': body(sign),
            'body_source': 'original Native CARLA actor transform and bounding box',
            'phase_source': 'constructed controller phase; original body geometry independently checked'}
