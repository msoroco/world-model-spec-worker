"""Inspect the authored C295180 approach and the operative stop line."""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def inspect(path):
    root = ET.fromstring(Path(path).read_text())
    roads = {road.get('id'): road for road in root.findall('road')}
    if not {'1', '13', '3', '14'}.issubset(roads):
        raise ValueError('Connected T-intersection road inventory differs')
    approach = roads['1']
    geometry = approach.find('./planView/geometry')
    if geometry is None or geometry.find('line') is None or not math.isclose(
            float(geometry.get('hdg')), math.pi / 2, abs_tol=1e-8):
        raise ValueError('Signed subject approach geometry differs')
    if not math.isclose(float(geometry.get('y')), -240.0) or not math.isclose(
            float(approach.get('length')), 233.0):
        raise ValueError('Subject approach distance differs')
    lane = approach.find('./lanes/laneSection/right/lane')
    if lane is None or lane.get('id') != '-1' or lane.get('type') != 'driving':
        raise ValueError('Subject approach lane differs')
    objects = approach.findall('./objects/object')
    if any(obj.get('type') == 'crosswalk' for obj in objects):
        raise ValueError('Near-side crosswalk invalidates stop-line branch')
    lines = [obj for obj in objects if obj.get('name') == 'clearly-marked-stop-line'
             and obj.get('type') == 'roadMark']
    if len(lines) != 1 or not math.isclose(float(lines[0].get('s')), 229.0) or not math.isclose(
            float(lines[0].get('width')), 7.0):
        raise ValueError('Clearly marked transverse stop-line object absent')
    signs = [sign for sign in approach.findall('./signals/signal')
             if sign.get('name') == 'STOP' and sign.get('type') == '206'
             and sign.get('orientation') == '-']
    if len(signs) != 1 or not math.isclose(float(signs[0].get('s')), 222.0):
        raise ValueError('Governing stop-sign source differs')
    links = [connection.get('incomingRoad') for connection in root.findall(
        './junction/connection')]
    if '1' not in links or '3' not in links:
        raise ValueError('T-intersection connection to subject and cross traffic absent')
    return {'format': 'c295180-road-source-review-v1', 'approach_road_id': 1,
            'approach_lane_id': -1, 'near_crosswalk_present': False,
            'stop_line_object_id': lines[0].get('id'), 'stop_line_world_y_m': -11.0,
            'stop_sign_signal_id': signs[0].get('id'),
            'intersection_near_boundary_world_y_m': -7.0,
            'physical_rendering_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--road', required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.road), sort_keys=True))
