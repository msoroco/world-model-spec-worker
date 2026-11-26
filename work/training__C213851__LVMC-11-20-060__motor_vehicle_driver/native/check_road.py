"""Check authored road, sidewalk and driveway surface geometry on CPU."""

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from build_requests import ROOT, sha


ROAD = ROOT / 'native/road/road.xodr'


def check(path=ROAD):
    path = Path(path)
    tree = ET.parse(path).getroot()
    if tree.tag != 'OpenDRIVE':
        raise ValueError('Authored road is not OpenDRIVE')
    roads = {int(road.attrib['id']): road for road in tree.findall('road')}
    if set(roads) != {1, 2}:
        raise ValueError('Roadway and private driveway surfaces missing')
    main, driveway = roads[1], roads[2]
    main_geometry = main.find('planView/geometry')
    driveway_geometry = driveway.find('planView/geometry')
    if (float(main_geometry.attrib['length']) < 100 or
            abs(float(main_geometry.attrib['x']) + 70) > 1e-8 or
            abs(float(main_geometry.attrib['hdg'])) > 1e-8 or
            abs(float(driveway_geometry.attrib['x'])) > 1e-8 or
            abs(float(driveway_geometry.attrib['y']) + 3.5) > 1e-8 or
            abs(float(driveway_geometry.attrib['hdg']) + math.pi / 2) > 1e-8 or
            float(driveway_geometry.attrib['length']) < 10):
        raise ValueError('Road-to-driveway geometry differs')
    right = main.find('lanes/laneSection/right')
    lane_types = {int(lane.attrib['id']): lane.attrib['type']
                  for lane in right.findall('lane')}
    if lane_types.get(-1) != 'driving' or lane_types.get(-2) != 'sidewalk':
        raise ValueError('Main driving lane and sidewalk surface missing')
    widths = {int(lane.attrib['id']): float(lane.find('width').attrib['a'])
              for lane in right.findall('lane')}
    if abs(widths[-1] - 3.5) > 1e-8 or abs(widths[-2] - 2.0) > 1e-8:
        raise ValueError('Sidewalk boundary widths differ')
    if not driveway.findall('lanes/laneSection/right/lane'):
        raise ValueError('Private driveway driving surface missing')
    return {'format': 'road-to-driveway-authored-geometry-check',
            'passed': True, 'road_sha256': sha(path),
            'main_driving_lane_right_edge_y_m': -3.5,
            'sidewalk_y_interval_m': [-5.5, -3.5],
            'driveway_crosses_sidewalk_polygon': True,
            'carla_mesh_realization_observed': False,
            'private_property_or_district_legally_verified': False}


if __name__ == '__main__':
    print(json.dumps(check()))
