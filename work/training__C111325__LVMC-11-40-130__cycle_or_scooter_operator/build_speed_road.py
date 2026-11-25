"""Rotate the source-hashed C111325 stop-sign approach to the x-axis.

The sign remains the same OpenDRIVE signal on the same incoming road. The
translation places its road position at x=0 so the bicycle target x=-2 m is
physically before the sign on the governed approach.
"""
import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path('work/training__C111325__NRS-484A-450-2__motor_vehicle_driver/native/road.xodr')
SOURCE_SHA256 = '3605e0870932dcc7abc566e9253abe368b0ea0e332bb6bb8f1281e45949d7099'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(output):
    if sha(SOURCE) != SOURCE_SHA256:
        raise ValueError('Source C111325 stop-sign road changed')
    root = ET.parse(SOURCE).getroot()
    for geometry in root.findall('./road/planView/geometry'):
        x, y, heading = (float(geometry.attrib[key]) for key in ('x', 'y', 'hdg'))
        geometry.set('x', str(y+18.0))
        geometry.set('y', str(-x))
        geometry.set('hdg', str((heading-math.pi/2) % (2*math.pi)))
    header = root.find('header')
    header.set('name', 'C111325-bicycle-speed-stop-approach')
    tree = ET.ElementTree(root)
    tree.write(output, encoding='unicode')
    output.write_text(output.read_text()+'\n')
    return check(output)


def check(path):
    root = ET.parse(path).getroot()
    road = next(r for r in root.findall('road') if r.get('id') == '1')
    geo = road.find('planView/geometry')
    sign = next(s for s in road.findall('signals/signal') if s.get('name') == 'STOP')
    crossing = next(c for c in road.findall('objects/object') if c.get('type') == 'crosswalk')
    start_x, heading, sign_s, crossing_s = (float(v) for v in (
        geo.get('x'), geo.get('hdg'), sign.get('s'), crossing.get('s')))
    sign_x = start_x + sign_s*math.cos(heading)
    crossing_x = start_x + crossing_s*math.cos(heading)
    lanes = {int(l.get('id')) for l in road.findall('lanes/laneSection/right/lane')}
    if (abs(start_x+222)>1e-5 or abs(heading)>1e-5 or
            abs(sign_x)>1e-5 or abs(crossing_x-3)>1e-5 or -1 not in lanes or
            not start_x < -50 < -2 < sign_x < crossing_x):
        raise ValueError('Bicycle road/stop geometry differs')
    return {'format': 'c111325-speed-road-geometry-cpu-v1', 'passed': True,
            'source_sha256': SOURCE_SHA256, 'road_sha256': sha(path),
            'approach_start_x_m': start_x, 'stop_sign_x_m': sign_x,
            'crosswalk_start_x_m': crossing_x, 'bicycle_stop_target_x_m': -2.0,
            'approach_lane_id': -1, 'native_readback_pending': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--proof', type=Path, required=True)
    args = parser.parse_args()
    proof = build(args.output)
    args.proof.write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps({'passed': True, 'stop_sign_x_m': proof['stop_sign_x_m']}))


if __name__ == '__main__':
    main()
