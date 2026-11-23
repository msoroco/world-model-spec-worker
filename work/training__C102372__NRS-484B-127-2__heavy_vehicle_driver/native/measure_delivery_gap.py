"""Source-bound 30-second truck gap measurement for a future selected case.

This measures original geometry and time joins. It never determines whether
conditions permit a gap or whether any recording is legally acceptable.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from measure_gap import GAP_LIMIT_M, WIDTH_MIN_M, polygon, road_distance

FRAMES = 600
RATE_HZ = 20
NAMES = ('native_samples.jsonl', 'following_context.json', 'road.xodr')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(source):
    source = Path(source)
    manifest_path = source / 'source-manifest.json'
    if not manifest_path.is_file():
        raise ValueError('Missing original source manifest')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('format') != 'c102372-truck-follow-source-v1' or set(manifest.get('sha256', {})) != set(NAMES):
        raise ValueError('Wrong or incomplete original source manifest')
    for name in NAMES:
        path = source / name
        if not path.is_file() or digest(path) != manifest['sha256'][name]:
            raise ValueError('Original source missing or changed: ' + name)
    context = json.loads((source / 'following_context.json').read_text())
    if context.get('source_kind') not in ('synthetic_cpu_fixture', 'native_observation'):
        raise ValueError('Unknown source kind')
    if (context.get('road_id'), context.get('lane_id'), context.get('same_direction_lane_count'),
            context.get('overtaking')) != (1, -1, 1, False):
        raise ValueError('Qualifying single-lane following context differs')
    if context.get('conditions_permit_source') not in ('synthetic_assertion', 'original_observation'):
        raise ValueError('Conditions source status missing')
    root = ET.parse(source / 'road.xodr').getroot()
    road = root.find('road')
    if road is None:
        raise ValueError('Original road missing')
    profile = road.findall('elevationProfile/elevation')
    if [float(p.get('s', 'nan')) for p in profile] != [0, 100, 150, 200] or \
            [float(p.get('a', 'nan')) for p in profile] != [0, 0, 4, 0]:
        raise ValueError('Original hill crest differs')
    if [l.get('id') for l in road.findall('lanes/laneSection/right/lane')] != ['-1'] or \
            [l.get('id') for l in road.findall('lanes/laneSection/left/lane')] != ['1']:
        raise ValueError('Original directional lanes differ')
    rows = [json.loads(line) for line in (source / NAMES[0]).read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame original source required')
    distances = []
    for index, row in enumerate(rows):
        if row.get('native_frame') != index or not math.isclose(
                float(row.get('time_s', -1)), index / RATE_HZ, abs_tol=.002):
            raise ValueError('Original 600-frame time join differs at ' + str(index))
        actors = [row.get('ego'), row.get('lead')]
        if any(not isinstance(actor, dict) for actor in actors):
            raise ValueError('Original truck actor missing at ' + str(index))
        bodies = []
        for name, actor in zip(('ego', 'lead'), actors):
            if (actor.get('actor_class'), actor.get('road_id'), actor.get('lane_id')) != \
                    ('truck_or_combination', 1, -1):
                raise ValueError('Original truck class or lane differs: ' + name)
            speed = float(actor.get('speed_mps', float('nan')))
            if not math.isfinite(speed) or speed <= 0:
                raise ValueError('Original truck movement differs: ' + name)
            body = polygon(actor.get('body_xy_m'), name)
            width = max(y for _, y in body) - min(y for _, y in body)
            if width < WIDTH_MIN_M:
                raise ValueError('Truck below 80-inch width: ' + name)
            bodies.append(body)
        ego, lead = bodies
        ego_front = max(x for x, _ in ego)
        lead_back = min(x for x, _ in lead)
        if lead_back <= ego_front:
            raise ValueError('Lead not ahead with positive body gap')
        if min(max(y for _, y in ego), max(y for _, y in lead)) <= \
                max(min(y for _, y in ego), min(y for _, y in lead)):
            raise ValueError('Trucks lack lateral following overlap')
        distances.append(road_distance(ego_front, lead_back, profile))
    low, high = min(distances), max(distances)
    relation = 'above' if low > GAP_LIMIT_M + .1 else \
        'below' if high < GAP_LIMIT_M - .1 else 'boundary_unresolved'
    return {'format': 'c102372-delivery-window-gap-v1', 'frames': FRAMES, 'rate_hz': RATE_HZ,
            'duration_s': FRAMES / RATE_HZ, 'source_manifest_sha256': digest(manifest_path),
            'source_sha256': manifest['sha256'], 'minimum_road_gap_m': round(low, 6),
            'maximum_road_gap_m': round(high, 6),
            'median_road_gap_m': round(statistics.median(distances), 6),
            'threshold_m': GAP_LIMIT_M, 'relation_to_500ft': relation,
            'source_kind': context['source_kind'], 'legal_verdict_claimed': False,
            'physical_conditions_verified': False, 'physical_pixels_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.source), sort_keys=True))
