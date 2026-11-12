"""CARLA-lazy, source-bound physical turn-course indication placement.

The source record states an authorization claim. Native spawn/readback only
checks construction; original image and municipal review remain separate.
"""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

FORMS = ('marker', 'button', 'other_indication')


def _inside(point, polygon):
    x, y = point
    crossing = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            at_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < at_x:
                crossing = not crossing
    return crossing


def _point(value):
    if (not isinstance(value, list) or len(value) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not isfinite(v) for v in value)):
        raise ValueError('Nonfinite intersection or course point')
    return value


def load_source(path, expected_sha256, kind):
    if kind not in FORMS:
        raise ValueError('Unknown turn indication form')
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Turn indication source hash changed')
    record = json.loads(raw)
    if (not record.get('authority_document') or not record.get('intersection_id')
            or not record.get('map_name') or record.get('indication_form') != kind):
        raise ValueError('Turn indication authority, map or form source missing')
    polygon = record.get('intersection_polygon_xy_m')
    course = record.get('indicated_course_xy_m')
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError('Sourced intersection polygon missing')
    if not isinstance(course, list) or len(course) < 3:
        raise ValueError('Sourced turn course missing')
    polygon = [_point(point) for point in polygon]
    course = [_point(point) for point in course]
    if not any(_inside(point, polygon) for point in course[1:-1]):
        raise ValueError('Indicated course does not cross sourced intersection')
    objects = record.get('indications')
    if not isinstance(objects, list) or not objects:
        raise ValueError('No physical turn indications specified')
    allowed = record.get('form_blueprints', {}).get(kind)
    if not isinstance(allowed, list) or not allowed:
        raise ValueError('Indication form lacks sourced blueprint mapping')
    for item in objects:
        if (item.get('form') != kind or item.get('blueprint_id') not in allowed
                or not all(key in item for key in ('x', 'y', 'z', 'yaw'))):
            raise ValueError('Physical indication form or blueprint differs from source')
        values = [item[key] for key in ('x', 'y', 'z', 'yaw')]
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not isfinite(v) for v in values):
            raise ValueError('Nonfinite physical indication placement')
        if not _inside([item['x'], item['y']], polygon):
            raise ValueError('Indication falls outside sourced intersection')
    return record


def place_indications(world, source_path, expected_sha256, kind, make_transform):
    record = load_source(source_path, expected_sha256, kind)
    if world.get_map().name != record['map_name']:
        raise ValueError('Native map differs from sourced intersection')
    actors = []
    try:
        for item in record['indications']:
            transform = make_transform(*(item[key] for key in ('x', 'y', 'z', 'yaw')))
            waypoint = world.get_map().get_waypoint(transform.location)
            if waypoint is None or not waypoint.is_junction:
                raise ValueError('Indication does not occupy a Native junction')
            blueprint = world.get_blueprint_library().find(item['blueprint_id'])
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError('Native indication spawn failed')
            actors.append(actor)
            actual = actor.get_transform().location
            if max(abs(float(getattr(actual, axis)) - float(item[axis]))
                   for axis in ('x', 'y')) > .05:
                raise ValueError('Native indication position readback differs')
        return {'actors': actors, 'intersection_id': record['intersection_id'],
                'indication_form': kind, 'source_sha256': expected_sha256,
                'physical_xy_m': [[float(a.get_transform().location.x),
                                   float(a.get_transform().location.y)] for a in actors],
                'authorization_verified_by_worker': False,
                'visible_pixels_verified': False}
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise
