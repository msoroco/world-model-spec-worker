"""One-way street, sidewalk and fixture bounds for C150668 Native draft."""
import xml.etree.ElementTree as ET

FIXTURE_BOUNDS = {'min_x': 0.0, 'max_x': 2.0, 'min_y': 0.0, 'max_y': 2.0}
SIDEWALK_BOUNDS = {'min_x': -20.0, 'max_x': 20.0, 'min_y': 0.0, 'max_y': 3.0}


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C150668 sidewalk fixture',
                  version='1.00', date='2026-11-24', north='0', south='0', east='80', west='-80')
    road = ET.SubElement(root, 'road', id='1', name='one-way-fixture-street', length='160', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-80', y='0', hdg='0', length='160')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='1', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    sidewalk_lane = ET.SubElement(left, 'lane', id='1', type='sidewalk', level='false')
    ET.SubElement(sidewalk_lane, 'width', sOffset='0', a='3.0', b='0', c='0', d='0')
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
    lanes = root.findall('road/lanes/laneSection/right/lane')
    sidewalks = root.findall('road/lanes/laneSection/left/lane')
    if (road.attrib['length'] != '160' or
            [(int(l.attrib['id']), l.attrib['type']) for l in lanes] != [(-1, 'driving')] or
            [(int(l.attrib['id']), l.attrib['type']) for l in sidewalks] != [(1, 'sidewalk')]):
        raise ValueError('one-way fixture road contract changed')
    if not (SIDEWALK_BOUNDS['min_x'] <= FIXTURE_BOUNDS['min_x'] < FIXTURE_BOUNDS['max_x'] <= SIDEWALK_BOUNDS['max_x']):
        raise ValueError('fixture/sidewalk geometry changed')
    return {'road_id': 1, 'lane_id': -1, 'fixture_bounds_m': FIXTURE_BOUNDS,
            'sidewalk_bounds_m': SIDEWALK_BOUNDS,
            'native_readback_observed': False, 'fixture_identity_observed': False}
