"""Authored two same-direction marked lanes for the C230259 core encounter."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C230259-left-lane',
                  version='1', date='2026-11-25', north='20', south='-20',
                  east='800', west='-100', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='two-lane-same-direction',
                         length='900', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-100', y='0', hdg='0', length='900')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, mark in ((-1, 'broken'), (-2, 'solid')):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type=mark, color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    road = ET.fromstring(open_drive()).find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    actual = [(int(lane.attrib['id']), lane.attrib['type'],
               float(lane.find('width').attrib['a']), lane.find('roadMark').attrib['type'])
              for lane in lanes]
    if road.attrib['length'] != '900' or actual != [
            (-1, 'driving', 3.5, 'broken'), (-2, 'driving', 3.5, 'solid')]:
        raise ValueError('Authored two-lane road differs')
    return {'road_id': 1, 'same_direction_marked_lane_count': 2,
            'extreme_left_lane_id': -1, 'right_lane_id': -2,
            'controlled_access_original_verified': False,
            'posted_limit_original_verified': False}
