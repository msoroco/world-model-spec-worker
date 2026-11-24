"""Two parallel authored lanes for the C143691 trail/right-of-way draft."""
import xml.etree.ElementTree as ET

TRAIL_BOUNDS = {'min_x': -50.0, 'max_x': 70.0, 'min_y': -2.0, 'max_y': 2.0}
BARRIER_X_M = 8.0
BARRIER_CLEAR_GAP_M = 3.5


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C143691 trail access',
                  version='1.00', date='2026-11-24', north='0', south='0', east='80', west='-80')
    road = ET.SubElement(root, 'road', id='1', name='road-with-trail-access', length='160', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-80', y='8', hdg='0', length='160')
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
    for lane_id, kind in ((-1, 'driving'), (-2, 'biking')):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='4', b='0', c='0', d='0')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = root.findall('road/lanes/laneSection/right/lane')
    if road.attrib['length'] != '160' or [(int(l.attrib['id']), l.attrib['type']) for l in lanes] != [(-1, 'driving'), (-2, 'biking')]:
        raise ValueError('road/trail lane contract changed')
    if TRAIL_BOUNDS['min_y'] != -2 or TRAIL_BOUNDS['max_y'] != 2 or BARRIER_CLEAR_GAP_M < 2.5:
        raise ValueError('trail or barrier-gap contract changed')
    return {'road_id': 1, 'road_lane_id': -1, 'trail_lane_id': -2,
            'trail_right_of_way_m': TRAIL_BOUNDS, 'barrier_x_m': BARRIER_X_M,
            'barrier_clear_gap_m': BARRIER_CLEAR_GAP_M,
            'native_lane_readback_observed': False, 'official_designation_observed': False}
