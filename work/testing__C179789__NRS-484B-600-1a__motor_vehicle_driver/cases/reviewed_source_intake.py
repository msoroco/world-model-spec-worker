"""Structurally check eight selected Native road, weather and surface packets.

This verifies declared review and source bytes; it cannot verify Native truth.
"""
import argparse
import hashlib
import json
from pathlib import Path

SUFFIXES = ('dry_4mps', 'dry_open_traffic', 'dry_6mps', 'wet_same_traffic',
            'narrow_same_traffic', 'dense_traffic', 'low_visibility', 'ice_or_snow')


def sha(data):
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def declaration(value, field):
    if (not isinstance(value, str) or not value.strip() or
            any(word in value.lower() for word in ('synthetic', 'diagnostic'))):
        raise ValueError('Original Native review declaration required: ' + field)


def source_document(text, source, field):
    declaration(text, field)
    if not isinstance(source, dict) or source.get('sha256') != sha(text):
        raise ValueError('Original source hash changed: ' + field)
    if source.get('path') not in ('surface.txt', 'weather.json'):
        raise ValueError('Unexpected original source path: ' + field)


def validate_case(construction):
    files = {row['path']: row['content'] for row in construction['files']}
    required = {'config.json', 'road_packet.json', 'surface_packet.json',
                'surface-seed.txt', 'weather.json'}
    if not required <= set(files):
        raise ValueError('Selected Native source packet missing')
    config = json.loads(files['config.json'])
    road = json.loads(files['road_packet.json'])
    surface = json.loads(files['surface_packet.json'])
    weather = json.loads(files['weather.json'])
    case = construction['case_id']
    if (road.get('case_id') != case or config.get('selected_case_id') != case
            or road.get('review_status') != 'reviewed_native_road_site'
            or surface.get('review_status') != 'reviewed_native_surface'):
        raise ValueError('Original Native road/surface review required: ' + case)
    for key in ('reviewer', 'road_review_basis', 'traffic_review_basis',
                'camera_review_basis', 'native_map_id'):
        declaration(road.get(key), key)
    for key in ('reviewer', 'review_basis'):
        declaration(surface.get(key), key)
    if (type(road.get('road_id')) is not int or type(road.get('lane_id')) is not int
            or surface.get('native_map_id') != road['native_map_id']
            or surface.get('road_id') != road['road_id']
            or surface.get('surface') != config['condition_target']['surface']):
        raise ValueError('Selected Native road/surface identity or condition differs')
    source_document(files['surface-seed.txt'], surface.get('source'), 'surface')
    if (weather.get('native_map_id') != road['native_map_id']
            or weather.get('weather_profile') != road.get('weather_profile')):
        raise ValueError('Original Native weather profile or map differs')
    source_document(files['weather.json'], road.get('weather_profile_source'), 'weather')
    for key in ('ego_spawn', 'lead_spawn'):
        spawn = road.get(key)
        if not isinstance(spawn, dict) or any(type(spawn.get(axis)) not in (int, float)
                                                 for axis in ('x', 'y', 'z', 'yaw_deg')):
            raise ValueError('Original reviewed Native spawn missing: ' + key)
    return {'case_id': case, 'native_map_id': road['native_map_id'],
            'road_id': road['road_id'], 'lane_id': road['lane_id'],
            'surface_source_sha256': sha(files['surface-seed.txt']),
            'weather_source_sha256': sha(files['weather.json']),
            'road_packet_sha256': sha(files['road_packet.json'])}


def check(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    rows = {}
    for entry in manifest['cases']:
        construction = json.loads((folder / entry['construction']).read_text())
        row = validate_case(construction)
        suffix = row['case_id'].split('__')[-1]
        if suffix not in SUFFIXES or suffix in rows:
            raise ValueError('Exact selected case coverage differs')
        rows[suffix] = row
    if set(rows) != set(SUFFIXES):
        raise ValueError('Eight selected speed/condition packets required')
    speed = [rows[name] for name in ('dry_4mps', 'dry_open_traffic', 'dry_6mps')]
    for key in ('native_map_id', 'road_id', 'lane_id', 'surface_source_sha256',
                'weather_source_sha256'):
        if len({row[key] for row in speed}) != 1:
            raise ValueError('Fixed speed comparison source differs: ' + key)
    return {'format': 'worker-c179789-reviewed-source-intake', 'status': 'structural_only',
            'cases': rows, 'native_realization_verified': False,
            'camera_pixels_reviewed': False, 'legal_conclusion': 'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(check(args.folder), indent=2))
