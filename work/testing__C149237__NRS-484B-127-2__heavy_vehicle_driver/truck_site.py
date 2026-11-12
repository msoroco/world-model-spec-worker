"""CPU checked one-way site and exact initial truck body-gap placement.

The road is authored OpenDRIVE. Actual blueprint width, body lengths, traffic,
motion, legal highway status and source pixels need Native/source review.
"""
from pathlib import Path
import hashlib
import math
import xml.etree.ElementTree as ET


ROAD = Path(__file__).resolve().parent / 'native-map-plan/one-way-truck-road.xodr'
CLASS_MAP = Path(__file__).resolve().parents[2] / 'runtime/python/carla_sgg/actors.py'
TRUCK_BLUEPRINTS = ('vehicle.carlamotors.european_hgv', 'vehicle.carlamotors.carlacola')
GAP_TARGETS_M = {'gap_below_500ft': 150.0, 'gap_at_500ft': 152.4,
                 'gap_above_500ft': 155.0}
LANE_WIDTH_M = 3.8
ROAD_LENGTH_M = 800.0
EGO_S_M = 100.0
MIN_EDGE_MARGIN_M = 50.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_site():
    road = ET.parse(ROAD).getroot()
    if road.tag != 'OpenDRIVE':
        raise ValueError('Wrong authored road document')
    roads = road.findall('road')
    if len(roads) != 1:
        raise ValueError('Expected exactly one authored road')
    r = roads[0]
    if r.get('id') != '149237' or float(r.get('length')) != ROAD_LENGTH_M:
        raise ValueError('Wrong authored truck road identity or length')
    geometry = r.find('planView/geometry')
    if geometry is None or geometry.find('line') is None or any(
            float(geometry.get(key)) != value for key, value in
            {'s': 0, 'x': 0, 'y': 0, 'hdg': 0, 'length': ROAD_LENGTH_M}.items()):
        raise ValueError('Truck site is not the sourced straight approach')
    sections = r.findall('lanes/laneSection')
    if len(sections) != 1 or float(sections[0].get('s')) != 0:
        raise ValueError('Truck site has unexpected lane sections')
    driving = sections[0].findall('.//lane[@type="driving"]')
    if len(driving) != 1 or driving[0].get('id') != '-1':
        raise ValueError('Truck site is not a single forward driving lane')
    width = driving[0].find('width')
    if width is None or any(float(width.get(key)) != value for key, value in
            {'sOffset': 0, 'a': LANE_WIDTH_M, 'b': 0, 'c': 0, 'd': 0}.items()):
        raise ValueError('Truck lane width changed')
    classifications = CLASS_MAP.read_text()
    for bp in TRUCK_BLUEPRINTS:
        if f"'{bp}': 'truck'" not in classifications:
            raise ValueError('Selected blueprint lacks pinned truck classification: ' + bp)
    return {'road_source': str(ROAD.relative_to(Path(__file__).resolve().parents[2])),
            'road_sha256': sha(ROAD), 'class_source': str(CLASS_MAP.relative_to(Path(__file__).resolve().parents[2])),
            'class_sha256': sha(CLASS_MAP), 'road_id': 149237, 'lane_id': -1,
            'lane_width_m': LANE_WIDTH_M, 'same_direction_lane_count': 1,
            'blueprint_ids': list(TRUCK_BLUEPRINTS)}


def initial_pair(gap_case, ego_half_length_m, lead_half_length_m):
    """Return road coordinates from realized body lengths; no assumed truck size."""
    validate_site()
    if gap_case not in GAP_TARGETS_M:
        raise ValueError('Unknown exact gap case')
    lengths = (ego_half_length_m, lead_half_length_m)
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or
           not math.isfinite(x) or x <= 0 for x in lengths):
        raise ValueError('Realized vehicle half lengths required')
    gap = GAP_TARGETS_M[gap_case]
    ego_x = EGO_S_M
    lead_x = ego_x + ego_half_length_m + gap + lead_half_length_m
    if ego_x - ego_half_length_m < MIN_EDGE_MARGIN_M or lead_x + lead_half_length_m > ROAD_LENGTH_M - MIN_EDGE_MARGIN_M:
        raise ValueError('Truck bodies exceed sourced straight approach margins')
    return {'ego_center_xy_m': [ego_x, -LANE_WIDTH_M / 2],
            'lead_center_xy_m': [lead_x, -LANE_WIDTH_M / 2],
            'heading_deg': 0.0, 'lane_forward_xy': [1.0, 0.0],
            'planned_initial_body_gap_m': gap,
            'gap_case': gap_case, 'actual_spawn_and_motion': 'unverified'}


if __name__ == '__main__':
    import json
    import sys
    if len(sys.argv) != 2:
        raise SystemExit('usage: truck_site.py OUTPUT_JSON')
    proof = {'format': 'worker-truck-site-cpu-proof', 'site': validate_site(),
             'cases': {name: initial_pair(name, 5.0, 5.0) for name in GAP_TARGETS_M},
             'sample_half_lengths_m': {'ego': 5.0, 'lead': 5.0},
             'sample_lengths_are_realized_dimensions': False,
             'physical_acceptance': False}
    Path(sys.argv[1]).write_text(json.dumps(proof, indent=2) + '\n')
