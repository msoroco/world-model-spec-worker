"""Authored paved highway, frontage and indicated entrance footprint; authority remains external."""
import math
import xml.etree.ElementTree as ET

GATE_X_M = 0.0
HIGHWAY_EDGE_Y_M = -3.5
RAMP_START = (-22.0, -9.0)
RAMP_END = (22.0, 0.0)


def _road(root, road_id, name, start, heading, length, kind):
    road = ET.SubElement(root, 'road', id=str(road_id), name=name,
                         length=str(length), junction='-1')
    ET.SubElement(road, 'link')
    ET.SubElement(road, 'type', s='0', type=kind)
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x=str(start[0]), y=str(start[1]),
                             hdg=str(heading), length=str(length))
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(ET.SubElement(road, 'lanes'), 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C228131 entry request',
                  version='1', date='2026-11-25', north='20', south='-20',
                  east='120', west='-100', vendor='worker')
    _road(root, 1, 'highway candidate', (-100, 0), 0, 220, 'motorway')
    _road(root, 2, 'frontage approach', (-100, -9), 0, 220, 'town')
    dx, dy = RAMP_END[0] - RAMP_START[0], RAMP_END[1] - RAMP_START[1]
    _road(root, 3, 'authored entrance paving', RAMP_START,
          math.atan2(dy, dx), math.hypot(dx, dy), 'rural')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    if len(roads) != 3 or [r.get('id') for r in roads] != ['1', '2', '3']:
        raise ValueError('Highway/frontage/entrance geometry missing')
    if [r.find('type').get('type') for r in roads] != ['motorway', 'town', 'rural']:
        raise ValueError('Authored road classes differ')
    if not RAMP_START[1] < HIGHWAY_EDGE_Y_M < RAMP_END[1]:
        raise ValueError('Entrance paving does not cross highway edge')
    return {'road_ids': [1, 2, 3], 'gate_x_m': GATE_X_M,
            'highway_edge_y_m': HIGHWAY_EDGE_Y_M,
            'paved_entrance_crosses_edge': True,
            'native_lane_connectivity_verified': False,
            'controlled_access_or_official_authority_verified': False}
