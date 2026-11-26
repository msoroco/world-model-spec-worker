"""Check the selected two-direction request without importing CARLA."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from route import FRAMES, RATE_HZ, SETTINGS


def check(root=Path('.')):
    root = Path(root)
    road = ET.fromstring((root / 'road.xodr').read_text())
    ways = road.findall('road')
    if road.tag != 'OpenDRIVE' or len(ways) != 1:
        raise ValueError('One authored two-direction road required')
    way = ways[0]
    if way.get('id') != '230259' or float(way.get('length')) != 200:
        raise ValueError('Authored road identity or extent differs')
    lanes = way.findall('lanes/laneSection/*/lane')
    if {lane.get('id') for lane in lanes if lane.get('type') == 'driving'} != {'-1', '1'}:
        raise ValueError('One driving lane in each direction required')
    widths = [float(w.get('a')) for lane in lanes for w in lane.findall('width')]
    if widths != [4.0, 4.0]:
        raise ValueError('Paved lane widths differ')
    config = json.loads((root / 'config.json').read_text())
    case = config['selected_case_id'].rsplit('__', 1)[-1]
    if case not in SETTINGS or config['rate_hz'] != RATE_HZ or config['duration_s'] != 30:
        raise ValueError('Exact selected duration or case differs')
    if [(c['name'], c['width'], c['height']) for c in config['cameras']] != [
        ('overview', 1920, 1080), ('approach', 1280, 720),
        ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]:
        raise ValueError('Pinned four-camera profile differs')
    rows = [json.loads(line) for line in (root / 'request.jsonl').read_text().splitlines()]
    if len(rows) != FRAMES or [r['frame'] for r in rows] != list(range(FRAMES)):
        raise ValueError('Complete requested motion missing')
    if any(r['requested_ego_lateral_center_y_m'] != SETTINGS[case] or
           r['ego_lane_id'] != -1 or r['oncoming_lane_id'] != 1 or
           r['ego_heading_deg'] != 0 or r['oncoming_heading_deg'] != 180 or
           r['native_observed'] or r['legal_verdict'] is not None for r in rows):
        raise ValueError('Comparison variable or opposite-direction provenance differs')
    if rows[0]['ego_center_xyz_m'][0] != -60 or rows[-1]['ego_center_xyz_m'][0] <= 0:
        raise ValueError('Ego does not traverse meeting road')
    if rows[0]['oncoming_center_xyz_m'][0] != 60 or rows[-1]['oncoming_center_xyz_m'][0] >= 0:
        raise ValueError('Other does not approach oppositely')
    if any(r['oncoming_center_xyz_m'][1] != 3.1 for r in rows):
        raise ValueError('Opposing vehicle position changed across comparison')
    return {'case_id': config['selected_case_id'], 'frames': FRAMES,
            'authored_paved_width_m': sum(widths), 'native_observed': False}
