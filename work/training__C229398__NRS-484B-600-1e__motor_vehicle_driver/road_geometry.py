"""Straight original-capture proposal with a same-road curb parking lane."""
import xml.etree.ElementTree as ET

ROAD_ID = 229398
DRIVING_LANE = -1
PARKING_LANE = -2
START_X_M = -900.0
LENGTH_M = 1800.0
DRIVING_Y_M = -1.75
PARKING_Y_M = -5.0
PARKING_X_M = 600.0


def road_xml():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C229398-approach-to-curb', version='1', north='4',
                  south='-9', east='900', west='-900', vendor='worker')
    road = ET.SubElement(root, 'road', id=str(ROAD_ID), name='approach_to_curb',
                         length=str(LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0',
                  x=str(START_X_M), y='0', hdg='0', length=str(LENGTH_M)).append(ET.Element('line'))
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(ET.SubElement(section, 'left'), 'lane', id='1', type='none', level='false')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width, mark in ((DRIVING_LANE, 'driving', 3.5, 'broken'),
                                       (PARKING_LANE, 'parking', 3.0, 'solid')):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type=mark, color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    road = ET.fromstring(road_xml()).find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    if road.get('id') != str(ROAD_ID) or float(road.get('length')) != LENGTH_M:
        raise ValueError('Wrong exact road or length')
    if [(int(lane.get('id')), lane.get('type'), float(lane.find('width').get('a')))
            for lane in lanes] != [(-1, 'driving', 3.5), (-2, 'parking', 3.0)]:
        raise ValueError('Driving and curb parking topology changed')
    return {'road_id': ROAD_ID, 'length_m': LENGTH_M, 'driving_lane': DRIVING_LANE,
            'parking_lane': PARKING_LANE, 'original_native_readback_pending': True}
