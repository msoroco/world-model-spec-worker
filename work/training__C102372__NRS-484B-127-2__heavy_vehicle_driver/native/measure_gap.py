"""Measure original-frame full-body truck gaps; never assign a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

RATE_HZ = 20
FRAMES = 480
WIDTH_MIN_M = 80 * 0.0254
GAP_LIMIT_M = 500 * 0.3048


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def polygon(value, name):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Missing original body: ' + name)
    points = []
    for xy in value:
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError('Invalid original body: ' + name)
        x, y = map(float, xy)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('Nonfinite original body: ' + name)
        points.append((x, y))
    if len(set(points)) != 4:
        raise ValueError('Degenerate original body: ' + name)
    return points


def road_distance(x0, x1, profile):
    """Distance along the authored road centerline elevation, not x projection."""
    steps = max(1, math.ceil((x1-x0)/0.25))
    step = (x1-x0)/steps
    total = 0.0
    for index in range(steps):
        station = x0 + (index+0.5)*step
        segment = max((row for row in profile if float(row.attrib['s']) <= station),
                      key=lambda row: float(row.attrib['s']))
        offset = station-float(segment.attrib['s'])
        slope = (float(segment.attrib['b']) + 2*float(segment.attrib['c'])*offset
                 + 3*float(segment.attrib['d'])*offset**2)
        total += math.sqrt(1+slope*slope)*step
    return total


def measure(source_dir):
    source_dir = Path(source_dir)
    manifest_path = source_dir / 'source-manifest.json'
    if not manifest_path.is_file():
        raise ValueError('Missing original source manifest')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('format') != 'c102372-truck-follow-source-v1':
        raise ValueError('Wrong truck-follow source format')
    names = ('native_samples.jsonl', 'following_context.json', 'road.xodr')
    if set(manifest.get('sha256', {})) != set(names):
        raise ValueError('Incomplete original source hash set')
    for name in names:
        path = source_dir / name
        if not path.is_file() or sha(path) != manifest['sha256'][name]:
            raise ValueError('Original source missing or changed: ' + name)
    try:
        road = ET.parse(source_dir / 'road.xodr').getroot().find('road')
        profile = road.findall('elevationProfile/elevation') if road is not None else []
        stations = [float(item.attrib['s']) for item in profile]
        heights = [float(item.attrib['a']) for item in profile]
        lanes = road.findall('lanes/laneSection/right/lane') if road is not None else []
        opposing = road.findall('lanes/laneSection/left/lane') if road is not None else []
    except (ET.ParseError, AttributeError, KeyError, ValueError) as error:
        raise ValueError('Invalid original hill-crest road') from error
    if stations != [0, 100, 150, 200] or heights != [0, 0, 4, 0] or \
            len(lanes) != 1 or len(opposing) != 1 or \
            lanes[0].get('id') != '-1' or opposing[0].get('id') != '1':
        raise ValueError('Wrong original hill-crest road or directional lanes')
    context = json.loads((source_dir / 'following_context.json').read_text())
    if context.get('source_kind') not in ('synthetic_cpu_fixture', 'native_observation'):
        raise ValueError('Unknown source kind')
    if context.get('road_id') != 1 or context.get('lane_id') != -1:
        raise ValueError('Following road or lane differs')
    if context.get('same_direction_lane_count') != 1 or context.get('overtaking') is not False:
        raise ValueError('Wrong statutory context for 500-foot witness')
    if context.get('conditions_permit_source') not in ('synthetic_assertion', 'original_observation'):
        raise ValueError('Missing conditions-permit source status')
    rows = [json.loads(line) for line in (source_dir / 'native_samples.jsonl').read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Full 480-frame original source required')
    gaps = []
    road_gaps = []
    for index, row in enumerate(rows):
        if row.get('native_frame') != index or abs(float(row.get('time_s', -1))-index/RATE_HZ) > .002:
            raise ValueError('Original frame/time join differs')
        ego, lead = row.get('ego'), row.get('lead')
        if not isinstance(ego, dict) or not isinstance(lead, dict):
            raise ValueError('Missing original truck actor')
        for actor, name in ((ego, 'ego'), (lead, 'lead')):
            if actor.get('actor_class') != 'truck_or_combination' or actor.get('road_id') != 1 or actor.get('lane_id') != -1:
                raise ValueError('Original qualifying truck or lane differs: ' + name)
            if float(actor.get('speed_mps', 0)) <= 0:
                raise ValueError('Original following actor not moving: ' + name)
        ego_body, lead_body = polygon(ego.get('body_xy_m'), 'ego'), polygon(lead.get('body_xy_m'), 'lead')
        ego_x = [p[0] for p in ego_body]; lead_x = [p[0] for p in lead_body]
        ego_y = [p[1] for p in ego_body]; lead_y = [p[1] for p in lead_body]
        for ys, name in ((ego_y, 'ego'), (lead_y, 'lead')):
            if max(ys)-min(ys) < WIDTH_MIN_M:
                raise ValueError('Truck below 80-inch width: ' + name)
        if min(max(ego_y), max(lead_y))-max(min(ego_y), min(lead_y)) <= 0:
            raise ValueError('Lead not laterally on following path')
        gap = min(lead_x)-max(ego_x)
        if gap <= 0:
            raise ValueError('Lead not ahead with positive surface gap')
        gaps.append(gap)
        road_gaps.append(road_distance(max(ego_x), min(lead_x), profile))
    low, high = min(road_gaps), max(road_gaps)
    relation = 'above' if low > GAP_LIMIT_M + .1 else 'below' if high < GAP_LIMIT_M - .1 else 'boundary_unresolved'
    return {'format': 'c102372-truck-gap-measurement-v1', 'source_sha256': manifest['sha256'],
            'manifest_sha256': sha(manifest_path), 'frames': FRAMES, 'rate_hz': RATE_HZ,
            'min_surface_gap_m': round(low, 6), 'max_surface_gap_m': round(high, 6),
            'median_surface_gap_m': round(statistics.median(road_gaps), 6),
            'median_horizontal_gap_m': round(statistics.median(gaps), 6),
            'threshold_m': GAP_LIMIT_M, 'relation_to_500ft': relation,
            'both_80in_truck_classes_source_checked': True,
            'single_same_direction_lane_source_checked': True,
            'conditions_permit_source': context['conditions_permit_source'],
            'physical_conditions_verified': context['source_kind'] == 'native_observation' and context['conditions_permit_source'] == 'original_observation',
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.source), sort_keys=True))
