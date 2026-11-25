"""Straight 3.5 m roadway lane with 2.5 m right shoulder for exact C230259."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C230259-right-edge',
                  version='1', date='2026-11-23', north='20', south='-20',
                  east='130', west='-30', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='straight-roadway-and-shoulder',
                         length='160', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-30', y='0', hdg='0', length='160')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', 3.5), (-2, 'shoulder', 2.5)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    road = ET.fromstring(open_drive()).find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    if road.attrib['length'] != '160' or [(int(x.attrib['id']), x.attrib['type'],
            float(x.find('width').attrib['a'])) for x in lanes] != [
                (-1, 'driving', 3.5), (-2, 'shoulder', 2.5)]:
        raise ValueError('Authored right-roadway edge geometry differs')
    return {'road_id': 1, 'driving_lane_id': -1, 'shoulder_lane_id': -2,
            'nominal_right_roadway_edge_y_m': -3.5, 'native_readback_pending': True}
