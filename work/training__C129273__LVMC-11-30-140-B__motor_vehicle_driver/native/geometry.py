"""Authored elevated mountain road for the C129273 Native construction draft."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C129273 mountain road',
                  version='1.00', date='2026-11-24', north='0', south='0', east='120', west='-120')
    road = ET.SubElement(root, 'road', id='1', name='mountain-road', length='240', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-120', y='0', hdg='0', length='240')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='25', b='.025', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    lane = ET.SubElement(left, 'lane', id='1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    ids = [int(l.attrib['id']) for l in root.findall('road/lanes/laneSection/right/lane')]
    if road.attrib['length'] != '240' or ids != [-1]:
        raise ValueError('mountain-road route geometry changed')
    elevation = root.find('road/elevationProfile/elevation')
    if float(elevation.attrib['a']) < 20 or float(elevation.attrib['b']) <= 0:
        raise ValueError('elevated road source missing')
    return {'road_id': 1, 'ego_lane_id': -1, 'opposing_lane_id': 1,
            'length_m': 240, 'grade': float(elevation.attrib['b']),
            'native_readback_observed': False}
