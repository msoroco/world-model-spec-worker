"""Source-bound geometry for the LVMC 11.30.060(A) curb-cell crosswalk branch.

This measures marking occupancy only. Vehicle right-of-way, designated-place
prohibitions and statutory applicability require separate original evidence.
"""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def marking(path):
    root = ET.parse(path).getroot()
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].get('junction') != '-1':
        raise ValueError('Crosswalk branch road cell differs')
    road = roads[0]
    if road.get('length') != '40' or len(root.findall('.//junction')):
        raise ValueError('Crosswalk branch road length or junction differs')
    objects = road.findall('objects/object')
    if len(objects) != 1:
        raise ValueError('Exactly one original marked crossing required')
    obj = objects[0]
    if (obj.get('type'), obj.get('id'), obj.get('s'), obj.get('t'),
        obj.get('length'), obj.get('width')) != (
        'crosswalk', '101', '20', '0', '7', '3'):
        raise ValueError('Marked crossing source object differs')
    if abs(float(obj.get('hdg')) + math.pi/2) > 1e-9:
        raise ValueError('Marked crossing orientation differs')
    geometry = road.find('planView/geometry')
    if (geometry is None or geometry.find('line') is None or
        (geometry.get('x'), geometry.get('y'), geometry.get('length')) != ('0', '-20', '40') or
        abs(float(geometry.get('hdg')) - math.pi/2) > 1e-9):
        raise ValueError('Crosswalk branch road trajectory differs')
    # Reference road runs along +y from -20 to +20. The -90 degree object
    # heading puts the 7 m marking across x, with its 3 m depth along y.
    return {'x_min_m': -3.5, 'x_max_m': 3.5,
            'y_min_m': -1.5, 'y_max_m': 1.5,
            'authored_marking_observed': True, 'original_paint_pixels_observed': False}


def measure(folder):
    folder = Path(folder)
    road, context, samples = (folder / name for name in (
        'road-crosswalk.xodr', 'crosswalk-context.json', 'curb-samples.jsonl'))
    for path in (road, context, samples):
        if not path.is_file():
            raise ValueError('Missing crosswalk branch source: ' + path.name)
    mark = marking(road)
    info = json.loads(context.read_text())
    if (info.get('road_sha256') != sha(road) or
        info.get('curb_samples_sha256') != sha(samples)):
        raise ValueError('Crosswalk branch source hash differs')
    if info.get('frozen_cell') != {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'}:
        raise ValueError('Crosswalk branch frozen cell differs')
    if info.get('source_kind') not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Crosswalk branch provenance missing')
    rows = [json.loads(line) for line in samples.read_text().splitlines() if line.strip()]
    if len(rows) != 240:
        raise ValueError('Full crosswalk branch source required')
    first_entry = None
    previous = None
    vehicle_trace = []
    for row in rows:
        if (type(row.get('native_frame')) is not int or
            type(row.get('time_s')) not in (int, float) or
            not math.isfinite(row['time_s'])):
            raise ValueError('Crosswalk branch frame invalid')
        if previous is not None and (row['native_frame'] != previous['native_frame'] + 1 or
            abs(row['time_s'] - previous['time_s'] - .05) > .002):
            raise ValueError('Crosswalk branch frame order differs')
        body = row.get('pedestrian_footprint_xy_m')
        if not isinstance(body, list) or len(body) != 4 or any(
            not isinstance(v, list) or len(v) != 2 or any(
                type(n) not in (int, float) or not math.isfinite(n) for n in v) for v in body):
            raise ValueError('Crosswalk branch original footprint invalid')
        if (row.get('pedestrian_id') != info.get('pedestrian_id') or
            row.get('vehicle_id') != info.get('vehicle_id')):
            raise ValueError('Crosswalk branch actor identity differs')
        vehicle_trace.append((row['vehicle_xy_m'], row['vehicle_speed_mps']))
        if first_entry is None and max(v[0] for v in body) > -3.5:
            first_entry = row
        previous = row
    if first_entry is None:
        raise ValueError('Crosswalk branch roadway entry not observed')
    body = first_entry['pedestrian_footprint_xy_m']
    inside = (min(v[1] for v in body) >= mark['y_min_m'] and
              max(v[1] for v in body) <= mark['y_max_m'])
    outside = (min(v[1] for v in body) > mark['y_max_m'] or
               max(v[1] for v in body) < mark['y_min_m'])
    relation = 'inside_authored_marking' if inside else 'outside_authored_marking' if outside else 'boundary_ambiguous'
    return {'format': 'c230222-crosswalk-branch-geometry-v1',
            'source_sha256': {path.name: sha(path) for path in (road, context, samples)},
            'source_kind': info['source_kind'], 'marking': mark,
            'frames': len(rows), 'roadway_entry_frame': first_entry['native_frame'],
            'crossing_y_m': first_entry['pedestrian_xy_m'][1],
            'marking_relation_at_entry': relation,
            'vehicle_trace_sha256': hashlib.sha256(json.dumps(vehicle_trace, sort_keys=True).encode()).hexdigest(),
            'physical_crossing_observed': info['source_kind'] == 'native_observation',
            'vehicle_right_of_way_reviewed': False,
            'designated_place_prohibition_reviewed': False,
            'legal_applicability_conclusion': None}
