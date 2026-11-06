"""Authored C10316 crossing geometry checks; no legal highway designation."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROAD = HERE / 'road.xodr'
NEAR_X = -3.5
FAR_X = 3.5
CROSSWALK_ID = 'C10316-authored-alley-crosswalk'


def check(path=ROAD):
    root = ET.parse(path).getroot()
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].get('id') != '1':
        raise ValueError('Expected one authored C10316 crossing road')
    road = roads[0]
    geometry = road.find('planView/geometry')
    if geometry is None or geometry.find('line') is None or abs(float(geometry.get('hdg'))-math.pi/2) > 1e-8:
        raise ValueError('Crossing road reference direction differs')
    if abs(float(road.get('length'))-40) > 1e-8:
        raise ValueError('Crossing road length differs')
    section = road.find('lanes/laneSection')
    widths = {lane.get('id'): float(lane.find('width').get('a'))
              for lane in section.findall('left/lane') + section.findall('right/lane')}
    if widths != {'1': 3.5, '-1': 3.5}:
        raise ValueError('Authored roadway width differs from measured edges')
    objects = road.findall('objects/object')
    matched = [o for o in objects if o.get('name') == CROSSWALK_ID and o.get('type') == 'crosswalk']
    if len(matched) != 1:
        raise ValueError('Named crosswalk object missing')
    obj = matched[0]
    if any(abs(float(obj.get(key))-value) > 1e-8 for key, value in
           (('s', 20), ('t', 0), ('length', 3), ('width', 7))):
        raise ValueError('Named crosswalk dimensions or station differ')
    if abs(FAR_X-NEAR_X-7) > 1e-8:
        raise ValueError('Authored highway-edge span differs')
    return {'authored_road_id': 1, 'road_length_m': 40, 'road_width_m': 7,
            'crosswalk_id': CROSSWALK_ID, 'crosswalk_station_m': 20,
            'near_edge_x_m': NEAR_X, 'far_edge_x_m': FAR_X,
            'legal_highway_status_verified': False,
            'native_map_loaded': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
