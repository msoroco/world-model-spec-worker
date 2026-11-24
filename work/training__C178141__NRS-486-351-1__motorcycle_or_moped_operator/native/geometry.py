"""Paved adjacent lanes for C178141; physical clearance remains unverified."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C178141 adjacent lanes',
                  version='1.00', date='2026-11-24', north='0', south='0', east='80', west='-80')
    road = ET.SubElement(root, 'road', id='1', name='paved-two-lane-road', length='160', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-80', y='6', hdg='0', length='160')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='1', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id in (-1, -2):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3', b='0', c='0', d='0')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = root.findall('road/lanes/laneSection/right/lane')
    if road.attrib['length'] != '160' or [int(l.attrib['id']) for l in lanes] != [-1, -2]:
        raise ValueError('adjacent-lane geometry changed')
    return {'road_id': 1, 'lane_ids': [-1, -2], 'lane_centres_y_m': [4.5, 1.5],
            'lane_marking_y_m': 3.0, 'native_readback_observed': False,
            'physical_clearance_observed': False}
