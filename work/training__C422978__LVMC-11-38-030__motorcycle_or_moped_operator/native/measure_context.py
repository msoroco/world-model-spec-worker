"""Saved motorcycle body/sidewalk/city/driveway geometry; no legal conclusion."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing context source: ' + name)
    return path


def polygon(points):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError('Context polygon needs three vertices')
    vertices = []
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in point):
            raise ValueError('Context polygon has invalid coordinate')
        vertices.append((float(point[0]), float(point[1])))
    area = abs(sum(a[0] * b[1] - b[0] * a[1]
                   for a, b in zip(vertices, vertices[1:] + vertices[:1]))) / 2
    if area <= .01 or len(set(vertices)) != len(vertices):
        raise ValueError('Context polygon is degenerate')
    return vertices


def hull(points):
    unique = sorted(set(points))
    if len(unique) < 3:
        raise ValueError('Motorcycle body hull absent')
    lower, upper = [], []
    for point in unique:
        while len(lower) >= 2 and orientation(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(unique):
        while len(upper) >= 2 and orientation(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def body_points(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Motorcycle body needs four corners')
    points = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in point):
            raise ValueError('Motorcycle body coordinate invalid')
        points.append((float(point[0]), float(point[1])))
    return points


def transform(points, matrix):
    if (not isinstance(matrix, list) or len(matrix) != 2 or
            any(not isinstance(row, list) or len(row) != 3 for row in matrix) or
            any(not isinstance(value, (int, float)) or not math.isfinite(value)
                for row in matrix for value in row)):
        raise ValueError('Native-to-context affine transform invalid')
    a, b = matrix
    if abs(a[0] * b[1] - a[1] * b[0]) < 1e-9:
        raise ValueError('Native-to-context affine transform singular')
    return [(a[0]*x + a[1]*y + a[2], b[0]*x + b[1]*y + b[2]) for x, y in points]


def inside(point, vertices):
    x, y = point
    parity = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if ((a[1] > y) != (b[1] > y)) and x < (
                b[0]-a[0]) * (y-a[1]) / (b[1]-a[1]) + a[0]:
            parity = not parity
    return parity


def orientation(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def crossing(a, b, c, d):
    return orientation(a, b, c)*orientation(a, b, d) < 0 and \
           orientation(c, d, a)*orientation(c, d, b) < 0


def intersects(a, b):
    if any(inside(point, b) for point in a) or any(inside(point, a) for point in b):
        return True
    return any(crossing(u, v, p, q)
               for u, v in zip(a, a[1:] + a[:1])
               for p, q in zip(b, b[1:] + b[:1]))


def measure(folder, context):
    folder, context = Path(folder), Path(context)
    observed_path = source(folder, 'native-observed.jsonl')
    map_path = source(folder, 'native-map-readback.json')
    if not context.is_file():
        raise ValueError('Missing context source: city-context.json')
    packet = json.loads(context.read_text())
    if packet.get('format') != 'c422978-spatial-context-v1' or packet.get('law_id') != 'LVMC-11-38-030':
        raise ValueError('Spatial context identity differs')
    if packet.get('map_readback_sha256') != sha(map_path):
        raise ValueError('Spatial context map readback hash differs')
    if packet.get('authority_kind') not in ('synthetic_cpu', 'unreviewed_city_source'):
        raise ValueError('Spatial context authority kind unsupported')
    if packet.get('city_authority_reviewed') is not False:
        raise ValueError('City authority review cannot be claimed by packet')
    native_map = json.loads(map_path.read_text())
    if native_map.get('sidewalk_lane_id') != -2 or native_map.get('sidewalk_road_id') != 1:
        raise ValueError('Native sidewalk lane readback differs')
    sidewalk = polygon(packet.get('sidewalk_polygon'))
    city = polygon(packet.get('city_boundary_polygon'))
    driveways = packet.get('driveway_crossing_polygons')
    if not isinstance(driveways, list):
        raise ValueError('Driveway crossing inventory absent')
    driveways = [polygon(item) for item in driveways]
    matrix = packet.get('native_to_context_affine')
    transform([(0, 0)], matrix)
    rows = [json.loads(line) for line in observed_path.read_text().splitlines()]
    if len(rows) != 480:
        raise ValueError('Context observation frame count differs')
    sidewalk_frames, city_frames, driveway_frames, qualifying_geometry = [], [], [], []
    for index, row in enumerate(rows):
        if row.get('frame') != index or row.get('motorcycle_blueprint') != 'vehicle.kawasaki.ninja':
            raise ValueError('Context motorcycle identity or frame differs')
        body = hull(transform(body_points(row.get('body_native_xy_m')), matrix))
        if not isinstance(row.get('speed_mps'), (int, float)) or not math.isfinite(row['speed_mps']):
            raise ValueError('Context speed invalid')
        if row['speed_mps'] <= .1:
            continue
        on_sidewalk = intersects(body, sidewalk)
        in_city = intersects(body, city)
        on_driveway = any(intersects(body, footprint) for footprint in driveways)
        if on_sidewalk: sidewalk_frames.append(index)
        if in_city: city_frames.append(index)
        if on_driveway: driveway_frames.append(index)
        if on_sidewalk and in_city and not on_driveway: qualifying_geometry.append(index)
    return {'format': 'c422978-spatial-context-measurement-v1',
            'source_kind': rows[0]['source_kind'],
            'authority_kind': packet['authority_kind'],
            'frames': 480,
            'moving_sidewalk_intersection_frames': len(sidewalk_frames),
            'moving_city_boundary_intersection_frames': len(city_frames),
            'moving_driveway_crossing_intersection_frames': len(driveway_frames),
            'candidate_city_sidewalk_non_driveway_frames': len(qualifying_geometry),
            'city_authority_reviewed': False,
            'driveway_rule_composition_reviewed': False,
            'legal_verdict': None,
            'source_hashes': {'native-observed.jsonl': sha(observed_path),
                              'native-map-readback.json': sha(map_path),
                              'city-context.json': sha(context)}}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--context', required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.attempt, args.context), indent=2))
