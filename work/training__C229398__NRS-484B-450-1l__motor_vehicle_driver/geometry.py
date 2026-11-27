"""Authored road, curb and curbside parking position for C229398.

The XML is a construction request. Original highway and curb status require
independent map and authority readback after Native execution.
"""
import xml.etree.ElementTree as ET

CURB_START = [-100.0, -6.5]
CURB_END = [100.0, -6.5]
CURBSIDE_CENTER = [0.0, -5.2]
EGO_LATERAL = -1.75


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C229398 curb road',
                  version='1.00', date='2026-11-27', north='0', south='0', east='100', west='-100')
    road = ET.SubElement(root, 'road', id='1', name='curbside-double-parking', length='200', junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='-100', y='0', hdg='0', length='200')
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='1', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    positive = ET.SubElement(left, 'lane', id='1', type='driving', level='false')
    ET.SubElement(positive, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    travel = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(travel, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    parking = ET.SubElement(right, 'lane', id='-2', type='parking', level='false')
    ET.SubElement(parking, 'width', sOffset='0', a='3.0', b='0', c='0', d='0')
    ET.SubElement(parking, 'roadMark', sOffset='0', type='solid', weight='standard',
                  color='white', width='0.15')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    if [int(l.get('id')) for l in root.findall('road/lanes/laneSection/right/lane')] != [-1, -2]:
        raise ValueError('Travel and parking lane geometry changed')
    if root.find('road').get('length') != '200' or CURB_START[1] != CURB_END[1]:
        raise ValueError('Original curb segment missing')
    if not CURB_START[1] < CURBSIDE_CENTER[1] < -3.5 < EGO_LATERAL < 0:
        raise ValueError('Curbside-to-highway ordering changed')
    return {'road_id': 1, 'ego_lane_id': -1, 'curbside_lane_id': -2,
            'curb_start_xy_m': CURB_START, 'curb_end_xy_m': CURB_END,
            'road_interior_normal_sign': 1,
            'curbside_center_xy_m': CURBSIDE_CENTER,
            'highway_dedication_verified': False, 'native_readback_observed': False}
