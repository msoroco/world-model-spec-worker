"""Source-joined physical marker and original turning-course measurements."""

import argparse
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _inside(point, polygon):
    x, y = point
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < crossing:
                result = not result
    return result


def _distance(point, polyline):
    values = []
    for a, b in zip(polyline, polyline[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        if length2 <= 0:
            raise ValueError('Indicated course has degenerate segment')
        t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2))
        values.append(hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy))
    if not values:
        raise ValueError('Indicated course needs two points')
    return min(values)


def measure(source_dir, case_id):
    root = Path(source_dir)
    names = ('marked_intersection.json', 'turn_body.jsonl', 'video_frames.jsonl',
             'authority_source_original.json')
    paths = {name: root / name for name in names}
    if any(not path.is_file() for path in paths.values()):
        raise ValueError('Original marker, body, frame-map or authority source missing')
    scene = json.loads(paths[names[0]].read_text())
    authority_raw = paths['authority_source_original.json'].read_bytes()
    if sha256(authority_raw).hexdigest() != scene.get('authority_source_sha256'):
        raise ValueError('Original authority source hash changed')
    authority = json.loads(authority_raw)
    for source_key, scene_key in (
            ('municipal_jurisdiction_source', 'municipal_jurisdiction_source'),
            ('intersection_source', 'intersection_source'),
            ('authorization_source', 'authorization_source'),
            ('intersection_polygon_xy_m', 'intersection_polygon_xy_m'),
            ('indicated_course_xy_m', 'indicated_course_xy_m'),
            ('median_opening_with_intersecting_road', 'median_opening_with_intersecting_road')):
        if authority.get(source_key) != scene.get(scene_key):
            raise ValueError('Original authority source differs from captured scene: ' + source_key)
    if (scene.get('case_id') != case_id or not scene.get('municipal_jurisdiction_source')
            or not scene.get('intersection_source') or not scene.get('authorization_source')
            or scene.get('median_opening_with_intersecting_road') is not True):
        raise ValueError('Authorized municipal median-opening intersection source incomplete')
    polygon = scene['intersection_polygon_xy_m']
    form = scene.get('indication_form', 'marker')
    if form == 'marker':
        points = scene.get('physical_markers_xy_m')
        if scene.get('physical_indications_xy_m'):
            raise ValueError('Marker scene contains a non-marker readback')
    elif form in ('button', 'other_indication'):
        if authority.get('indication_form') != form or scene.get('physical_markers_xy_m'):
            raise ValueError('Original indication form differs from captured scene')
        points = scene.get('physical_indications_xy_m')
        expected = authority.get('indications')
        if (not isinstance(points, list) or not points
                or any(not isinstance(p, list) or len(p) != 2
                       or any(isinstance(v, bool) or not isinstance(v, (int, float))
                              or not isfinite(v) for v in p) for p in points)
                or not isinstance(expected, list) or not expected
                or len(expected) != len(points)):
            raise ValueError('Physical indication inventory differs from authority source')
        for point, item in zip(points, expected):
            if (not isinstance(item, dict) or item.get('form') != form or
                    any(isinstance(item.get(k), bool) or not isinstance(item.get(k), (int, float))
                        or not isfinite(item[k]) for k in ('x', 'y')) or
                    any(abs(point[i] - item[k]) > .05 for i, k in enumerate(('x', 'y')))):
                raise ValueError('Physical indication readback differs from original source')
    else:
        raise ValueError('Unsupported original indication form')
    if (len(polygon) < 3 or not isinstance(points, list) or not points
            or any(not isinstance(p, list) or len(p) != 2
                   or any(isinstance(v, bool) or not isinstance(v, (int, float))
                          or not isfinite(v) for v in p) for p in points)
            or not all(_inside(p, polygon) for p in points)):
        raise ValueError('Physical indications are not inside sourced intersection')
    course = scene['indicated_course_xy_m']
    bodies = [json.loads(line) for line in paths[names[1]].read_text().splitlines() if line.strip()]
    frames = [json.loads(line) for line in paths[names[2]].read_text().splitlines() if line.strip()]
    if not bodies or len(bodies) != len(frames):
        raise ValueError('Original turning path incomplete')
    rows = []
    for index, (body, frame) in enumerate(zip(bodies, frames)):
        if (frame.get('video_frame') != index or frame.get('carla_frame') != body.get('frame')
                or frame.get('time_s') != body.get('time_s')
                or body.get('actor_id') != scene.get('ego_actor_id')):
            raise ValueError('Original turn body/frame identity differs')
        corners = body.get('corners_xy_m')
        if not isinstance(corners, list) or len(corners) != 4:
            raise ValueError('Original body corners missing')
        centroid = [sum(p[axis] for p in corners) / 4 for axis in (0, 1)]
        rows.append({'frame': body['frame'], 'time_s': body['time_s'],
                     'inside_intersection': _inside(centroid, polygon),
                     'centroid_to_indicated_course_m': _distance(centroid, course),
                     'corner_to_indicated_course_m': [_distance(p, course) for p in corners]})
    if not any(row['inside_intersection'] for row in rows):
        raise ValueError('No original turn frame inside intersection')
    return {'case_id': case_id, 'indication_form': form,
            'physical_indications_xy_m': points,
            'frame_count': len(rows), 'observations': rows,
            'source_sha256': {name: sha256(path.read_bytes()).hexdigest()
                              for name, path in paths.items()},
            'direction_disobedience_legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = measure(args.source_dir, args.case_id)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
