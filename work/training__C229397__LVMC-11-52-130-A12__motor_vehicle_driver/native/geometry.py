"""Authored road and crosswalk extent; painted marking needs Native review."""
import json
import xml.etree.ElementTree as ET

CROSSWALK_RECT = [0.0, 4.0, -6.5, 0.0]
TARGET_X = {'controlled_1': -14.0, 'controlled_2': -5.0}


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C229397 crosswalk road',
                  version='1.00', date='2026-11-23', north='0', south='0', east='50', west='-50')
    road = ET.SubElement(root, 'road', id='1', name='paved-road-with-crosswalk', length='100', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                            s='0', x='-50', y='0', hdg='0', length='100')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='8', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', 3.5), (-2, 'parking', 3.0)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.10')
    objects = ET.SubElement(road, 'objects')
    ET.SubElement(objects, 'object', id='1', name='crosswalk-proposal', type='crosswalk',
                  s='50', t='-3.25', zOffset='0', hdg='0', roll='0', pitch='0',
                  length='4', width='6.5', height='0')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    crosswalk = road.find('objects/object')
    if road.attrib['length'] != '100' or [(int(l.attrib['id']), l.attrib['type']) for l in lanes] != [(-1, 'driving'), (-2, 'parking')]:
        raise ValueError('road/parking lane inventory differs')
    if crosswalk.attrib['type'] != 'crosswalk' or crosswalk.attrib['s'] != '50' or crosswalk.attrib['length'] != '4':
        raise ValueError('crosswalk proposal differs')
    if TARGET_X['controlled_1'] >= TARGET_X['controlled_2'] or CROSSWALK_RECT != [0.0, 4.0, -6.5, 0.0]:
        raise ValueError('controlled crosswalk targets differ')
    return {'passed': True, 'crosswalk_rect_xyxy_m': CROSSWALK_RECT,
            'target_centers_x_m': TARGET_X, 'road_length_m': 100,
            'native_marking_observed': False, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
