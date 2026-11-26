"""CPU-checkable one-way two-lane passing corridor with an unpaved right shoulder."""
import xml.etree.ElementTree as ET

ROAD_LENGTH_M = 350.0
LANE_WIDTH_M = 4.0
SHOULDER_WIDTH_M = 2.5
PAVED_RIGHT_EDGE_Y_M = -8.0
LEAD_LEFT_LANE_Y_M = -2.0
LEAD_RIGHT_LANE_Y_M = -6.0
EGO_PAVED_PASS_Y_M = -6.0
EGO_SHOULDER_PASS_Y_M = -8.7


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C178778-right-pass',
                  version='1', date='2026-11-26', north='20', south='-20',
                  east='350', west='0', vendor='scenario-worker')
    road = ET.SubElement(root, 'road', id='1', name='one-way-paved-two-lane',
                         length=str(ROAD_LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='0', y='0', hdg='0', length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', LANE_WIDTH_M),
                                 (-2, 'driving', LANE_WIDTH_M),
                                 (-3, 'shoulder', SHOULDER_WIDTH_M)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid' if lane_id != -1 else 'broken',
                      color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    if road.attrib['length'] != str(ROAD_LENGTH_M):
        raise ValueError('Right-pass road length changed')
    if [(int(l.attrib['id']), l.attrib['type'], float(l.find('width').attrib['a']))
            for l in lanes] != [(-1, 'driving', 4.0), (-2, 'driving', 4.0), (-3, 'shoulder', 2.5)]:
        raise ValueError('Paved lanes or unpaved shoulder changed')
    if root.findall('.//junction') or root.findall('.//signal'):
        raise ValueError('Passing corridor must remain uninterrupted')
    return {'road_length_m': ROAD_LENGTH_M, 'paved_driving_lanes': [-1, -2],
            'unpaved_shoulder_lane': -3, 'paved_right_edge_y_m': PAVED_RIGHT_EDGE_Y_M,
            'native_map_readback_observed': False, 'physical_pass_observed': False}
