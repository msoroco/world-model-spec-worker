"""Authored narrow public-park frontage geometry; public designation remains unsourced."""
import xml.etree.ElementTree as ET

PARK_BOUNDS = {'min_x': -20.0, 'max_x': 0.0, 'min_y': -7.0, 'max_y': 0.0}
STREET_BOUNDS = {'min_x': -100.0, 'max_x': 100.0, 'min_y': -7.0, 'max_y': 0.0}


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C135709 narrow road',
                  version='1.00', date='2026-11-24', north='0', south='0', east='100', west='-100')
    road = ET.SubElement(root, 'road', id='1', name='narrow-park-frontage', length='200', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-100', y='0', hdg='0', length='200')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='1', b='0', c='0', d='0')
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
    signals = ET.SubElement(road, 'signals')
    ET.SubElement(signals, 'signal', id='authored-no-parking-135709', s='80', t='-3.7',
                  name='NO_PARKING', dynamic='no', orientation='+', zOffset='0', country='US',
                  type='no_parking', subtype='0', value='0', unit='', height='0.8', width='0.6')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    ids = [int(l.attrib['id']) for l in root.findall('road/lanes/laneSection/right/lane')]
    if road.attrib['length'] != '200' or ids != [-1]:
        raise ValueError('narrow-road lane geometry changed')
    if not (PARK_BOUNDS['min_x'] < -10 < PARK_BOUNDS['max_x'] < 12):
        raise ValueError('frontage comparison stations changed')
    if root.find('road/signals/signal').attrib.get('name') != 'NO_PARKING':
        raise ValueError('Authored restriction device missing')
    return {'road_id': 1, 'ego_lane_id': -1, 'road_length_m': 200,
            'street_bounds_m': STREET_BOUNDS, 'park_bounds_m': PARK_BOUNDS,
            'official_device_status_observed': False, 'native_readback_observed': False}
