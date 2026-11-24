"""Exact C111331 crossing proposal. Geometry and states are requests, not observations."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C111331__NRS-484B-307-2b__pedestrian'
VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
CASES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
CROSSWALK = 'C111331-authored-marked-crosswalk'
TRAFFIC_HEAD = 'C111331-facing-circular-head'
PEDESTRIAN_HEAD = 'C111331-governing-pedestrian-head'


def proposal(suffix):
    if suffix not in CASES:
        raise ValueError('Unknown exact crossing case')
    contrary = suffix in ('witness_2', 'exception_1_2')
    return {
        'format': 'c111331-native-crossing-proposal-v1',
        'case_id': ASSIGNMENT + '__' + suffix,
        'cell': {'layout': 'intersection', 'maneuver': 'travel', 'control': 'traffic_light'},
        'actor': 'pedestrian', 'duration_s': 30, 'rate_hz': 20, 'frames': 600,
        'map': 'road.xodr', 'crosswalk_id': CROSSWALK,
        'traffic_head_id': TRAFFIC_HEAD, 'pedestrian_head_id': PEDESTRIAN_HEAD,
        'requested_traffic_indication': 'circular_green',
        'requested_pedestrian_indication': 'dont_walk' if contrary else 'walk',
        'requested_walker_start_xy_m': [0.0, -5.0],
        'requested_walker_direction_xy': [0.0, 1.0],
        'requested_walker_speed_mps': 1.05,
        'crosswalk_bounds_xy_m': [-1.5, -3.5, 1.5, 3.5],
        'cameras': [{'name': n, 'width': w, 'height': h} for n, w, h in VIEWS],
        'source_observation_required': [
            'Native walker identity and per-frame pose',
            'Native map crosswalk and pedestrian heading',
            'actual circular indication pixels and physical head governance',
            'actual pedestrian indication pixels and physical head governance',
            'four original RGB camera streams and frame hashes'],
        'scope': 'authored physical request; no Native execution or legal outcome asserted',
    }


def check_map(path=HERE / 'road.xodr'):
    root = ET.parse(path).getroot()
    roads = root.findall('road')
    if len(roads) != 2 or len(root.findall('junction')) != 1:
        raise ValueError('Two-road intersection and junction required')
    if {r.get('id') for r in roads} != {'1', '2'}:
        raise ValueError('Road identity differs')
    objects = [o for r in roads for o in r.findall('objects/object')]
    marks = [o for o in objects if o.get('name') == CROSSWALK and o.get('type') == 'crosswalk']
    if len(marks) != 1:
        raise ValueError('Named marked crosswalk missing')
    if marks[0].get('length') != '3' or marks[0].get('width') != '7':
        raise ValueError('Crosswalk width or depth differs')
    signals = [s for r in roads for s in r.findall('signals/signal')]
    if {s.get('name') for s in signals} != {TRAFFIC_HEAD, PEDESTRIAN_HEAD}:
        raise ValueError('Both named signal objects required')
    return {'authored_map_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'roads': 2, 'crosswalk': CROSSWALK, 'signals': 2,
            'native_map_loaded': False, 'signal_pixels_verified': False,
            'device_governance_verified': False}


def check_proposals():
    geometry = check_map()
    plans = [proposal(s) for s in CASES]
    fixed = ('cell', 'actor', 'duration_s', 'rate_hz', 'frames', 'map', 'crosswalk_id',
             'traffic_head_id', 'pedestrian_head_id', 'requested_traffic_indication',
             'requested_walker_start_xy_m', 'requested_walker_direction_xy',
             'requested_walker_speed_mps', 'crosswalk_bounds_xy_m', 'cameras')
    if any(plan[key] != plans[0][key] for plan in plans for key in fixed):
        raise ValueError('Comparison fixed conditions differ')
    if [p['requested_pedestrian_indication'] for p in plans] != [
            'walk', 'dont_walk', 'walk', 'dont_walk']:
        raise ValueError('Contrary pedestrian device variable differs')
    return {'geometry': geometry, 'cases': [p['case_id'] for p in plans],
            'comparison_variable': 'requested_pedestrian_indication',
            'source_observed': False}


if __name__ == '__main__':
    print(json.dumps(check_proposals(), sort_keys=True))
