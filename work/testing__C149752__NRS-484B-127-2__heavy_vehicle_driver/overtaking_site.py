"""Authored one-forward, one-opposing-lane passing site."""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

ROAD = Path(__file__).resolve().parent/'native-map-plan/overtaking-truck-road.xodr'


def validate_site():
    root = ET.parse(ROAD).getroot()
    roads = root.findall('road')
    if root.tag != 'OpenDRIVE' or len(roads) != 1:
        raise ValueError('Wrong overtaking road document')
    road = roads[0]
    if road.get('id') != '149239' or float(road.get('length', 'nan')) != 1200:
        raise ValueError('Wrong overtaking road identity or length')
    geometry = road.find('planView/geometry')
    if geometry is None or geometry.find('line') is None or any(
            float(geometry.get(key, 'nan')) != value for key, value in
            {'s': 0, 'x': 0, 'y': 0, 'hdg': 0, 'length': 1200}.items()):
        raise ValueError('Overtaking site is not straight')
    sections = road.findall('lanes/laneSection')
    if len(sections) != 1 or float(sections[0].get('s', 'nan')) != 0:
        raise ValueError('Unexpected overtaking lane sections')
    lanes = {int(lane.get('id')): lane for lane in sections[0].findall('.//lane[@type="driving"]')}
    if set(lanes) != {-1, 1}:
        raise ValueError('Overtaking needs one forward and one opposing lane')
    for lane in lanes.values():
        width = lane.find('width')
        if width is None or any(float(width.get(key, 'nan')) != value for key, value in
                {'sOffset': 0, 'a': 3.8, 'b': 0, 'c': 0, 'd': 0}.items()):
            raise ValueError('Overtaking lane width differs')
    return {'road_source': str(ROAD), 'road_sha256': hashlib.sha256(ROAD.read_bytes()).hexdigest(),
            'road_id': 149239, 'lane_id': -1, 'passing_lane_id': 1,
            'same_direction_lane_count': 1, 'lane_width_m': 3.8}
