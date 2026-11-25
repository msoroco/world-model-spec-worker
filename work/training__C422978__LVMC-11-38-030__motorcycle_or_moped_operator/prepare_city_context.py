"""Prepare a source-bound spatial packet for a fresh C422978 Native attempt.

The source is a surveyed GeoJSON FeatureCollection supplied with an explicit
native-to-source affine calibration. This tool makes no City or legal finding.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from measure_context import polygon, transform


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ring(feature):
    geometry = feature.get('geometry')
    if not isinstance(geometry, dict) or geometry.get('type') != 'Polygon':
        raise ValueError('Each surveyed feature must be a Polygon')
    coordinates = geometry.get('coordinates')
    if not isinstance(coordinates, list) or len(coordinates) != 1:
        raise ValueError('Polygon holes or missing rings require separate review')
    points = coordinates[0]
    if not isinstance(points, list) or len(points) < 4 or points[0] != points[-1]:
        raise ValueError('GeoJSON ring must close')
    vertices = points[:-1]
    polygon(vertices)
    # The saved measurement assumes a simple polygon.
    for i in range(len(vertices)):
        a, b = vertices[i], vertices[(i + 1) % len(vertices)]
        for j in range(i + 2, len(vertices)):
            if i == 0 and j == len(vertices) - 1:
                continue
            c, d = vertices[j], vertices[(j + 1) % len(vertices)]
            def orient(p, q, r):
                return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
            if orient(a, b, c)*orient(a, b, d) < 0 and orient(c, d, a)*orient(c, d, b) < 0:
                raise ValueError('Self-intersecting surveyed polygon')
    return vertices


def prepare(source, expected_sha, map_readback, calibration, output, diagnostic=False):
    source, map_readback, calibration, output = map(Path, (source, map_readback, calibration, output))
    if output.exists():
        raise ValueError('Use a fresh output packet')
    if sha(source) != expected_sha:
        raise ValueError('Survey source hash differs')
    data = json.loads(source.read_text())
    if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
        raise ValueError('Survey source must be a GeoJSON FeatureCollection')
    if data.get('city_authority_reviewed') is not False or not diagnostic and data.get('source_kind') != 'surveyed_city_source':
        raise ValueError('Survey provenance or authority claim invalid')
    crs = data.get('source_crs')
    if not isinstance(crs, str) or not crs.strip():
        raise ValueError('Source CRS absent')
    features = {}
    for feature in data['features']:
        if not isinstance(feature, dict) or not isinstance(feature.get('id'), str):
            raise ValueError('Survey feature ID absent')
        if feature['id'] in features:
            raise ValueError('Duplicate survey feature ID')
        features[feature['id']] = ring(feature)
    if set(features) < {'city_boundary', 'sidewalk'}:
        raise ValueError('City boundary or sidewalk feature absent')
    if any(name not in {'city_boundary', 'sidewalk'} and not name.startswith('driveway:') for name in features):
        raise ValueError('Unclassified survey feature')
    affine = json.loads(calibration.read_text())
    if affine.get('source_crs') != crs or affine.get('map_readback_sha256') != sha(map_readback):
        raise ValueError('Calibration CRS or Native map hash differs')
    matrix = affine.get('native_to_context_affine')
    transform([(0, 0)], matrix)
    if not diagnostic and matrix == [[1, 0, 0], [0, 1, 0]]:
        raise ValueError('Identity calibration requires diagnostic scope')
    if not isinstance(affine.get('calibration_source'), str) or not affine['calibration_source']:
        raise ValueError('Calibration source absent')
    if not diagnostic and not affine.get('reviewed_control_points'):
        raise ValueError('Original calibration control points absent')
    native_map = json.loads(map_readback.read_text())
    if native_map.get('sidewalk_road_id') != 1 or native_map.get('sidewalk_lane_id') != -2:
        raise ValueError('Native sidewalk readback differs')
    packet = {'format': 'c422978-spatial-context-v1', 'law_id': 'LVMC-11-38-030',
              'authority_kind': 'synthetic_cpu' if diagnostic else 'unreviewed_city_source',
              'city_authority_reviewed': False,
              'map_readback_sha256': sha(map_readback),
              'native_to_context_affine': matrix,
              'city_boundary_polygon': features['city_boundary'],
              'sidewalk_polygon': features['sidewalk'],
              'driveway_crossing_polygons': [features[k] for k in sorted(features) if k.startswith('driveway:')],
              'source_provenance': {'geojson_sha256': expected_sha, 'source_crs': crs,
                                    'feature_ids': sorted(features),
                                    'calibration_sha256': sha(calibration),
                                    'calibration_source': affine['calibration_source'],
                                    'diagnostic': diagnostic}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, indent=2, allow_nan=False) + '\n')
    return packet


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--map-readback', required=True)
    parser.add_argument('--calibration', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    prepare(args.source, args.source_sha256, args.map_readback, args.calibration, args.output, args.diagnostic)
