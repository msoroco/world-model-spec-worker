"""Authored C230222 road and curb checks; no legal road designation."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROAD = Path(__file__).resolve().parent / 'road.xodr'


def check(path=ROAD):
    root = ET.parse(path).getroot()
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].get('id') != '1':
        raise ValueError('Expected one authored C230222 road')
    road = roads[0]
    geometry = road.find('planView/geometry')
    if (geometry is None or geometry.find('line') is None or
        abs(float(geometry.get('hdg'))-math.pi/2) > 1e-8 or
        float(geometry.get('x')) != 0 or float(geometry.get('y')) != -20 or
        float(geometry.get('length')) != 40 or float(road.get('length')) != 40):
        raise ValueError('Authored road geometry differs')
    section = road.find('lanes/laneSection')
    widths = {lane.get('id'): float(lane.find('width').get('a'))
              for lane in section.findall('left/lane') + section.findall('right/lane')}
    if widths != {'1': 3.5, '-1': 3.5} or road.findall('objects/object'):
        raise ValueError('Curb road lanes or objects differ')
    return {'authored_road_id': 1, 'length_m': 40, 'width_m': 7,
            'curb_edge_x_m': -3.5, 'vehicle_lane_center_x_m': -1.75,
            'vehicle_conflict_y_m': 0, 'native_map_loaded': False,
            'legal_road_and_safety_place_status_verified': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
