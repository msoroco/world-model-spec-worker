"""Additional CPU map-authoring guard for the fixed red-X bus route."""
from pathlib import Path
import xml.etree.ElementTree as ET

from native_construction import LANE_WIDTH_M, ROAD_LENGTH_M, check_road


def check_fixed_map(path):
    basic = check_road(path)
    road = ET.parse(Path(path)).getroot().find('road')
    geometries = road.findall('./planView/geometry')
    if (len(geometries) != 1 or geometries[0].find('line') is None or
            any(float(geometries[0].attrib.get(key, 'nan')) != expected for key, expected in
                (('s', 0), ('x', 0), ('y', 0), ('hdg', 0), ('length', ROAD_LENGTH_M)))):
        raise ValueError('fixed straight route geometry differs')
    offsets = road.findall('./lanes/laneOffset')
    if len(offsets) != 1 or any(float(offsets[0].attrib.get(key, 'nan')) != 0
                                for key in ('s', 'a', 'b', 'c', 'd')):
        raise ValueError('fixed lane offset differs')
    for lane in road.findall('./lanes/laneSection/right/lane'):
        widths = lane.findall('width')
        if (len(widths) != 1 or
                float(widths[0].attrib.get('a', 'nan')) != LANE_WIDTH_M or
                any(float(widths[0].attrib.get(key, 'nan')) != 0
                    for key in ('sOffset', 'b', 'c', 'd'))):
            raise ValueError('source lane width differs from fixed route contract')
    return {**basic, 'fixed_geometry_checked': True,
            'constant_lane_width_checked': True}
