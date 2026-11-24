"""Draft one-way street with paired curb shoulders and left parking notice."""
import json
import xml.etree.ElementTree as ET

SIGN_NAME = 'NO STANDING OR PARKING LEFT SIDE'


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C135709-one-way-parking',
                  version='1', date='2026-11-23', north='12', south='-12', east='60', west='-60',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='one-way-street', length='120', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                            s='0', x='-60', y='0', hdg='0', length='120')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for parent, lane_id, kind, width in ((left, 1, 'shoulder', 3.0),
                                          (right, -1, 'driving', 3.5),
                                          (right, -2, 'shoulder', 3.0)):
        lane = ET.SubElement(parent, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.1')
    ET.SubElement(road, 'objects')
    signals = ET.SubElement(road, 'signals')
    ET.SubElement(signals, 'signal', id='493', s='15', t='3', name=SIGN_NAME,
                  dynamic='no', orientation='+', zOffset='2', country='USA',
                  type='parking_restriction', subtype='left_standing_or_parking',
                  value='0', unit='none', hOffset='0', pitch='0', roll='0')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/left/lane') + road.findall('lanes/laneSection/right/lane')
    signal = road.find('signals/signal')
    if [(int(l.attrib['id']), l.attrib['type']) for l in lanes] != [
            (1, 'shoulder'), (-1, 'driving'), (-2, 'shoulder')]:
        raise ValueError('one-way curb geometry changed')
    if signal is None or signal.attrib['name'] != SIGN_NAME or signal.attrib['orientation'] != '+':
        raise ValueError('left-side parking notice changed')
    return {'passed': True, 'road_id': 1, 'length_m': 120,
            'left_shoulder_lane_id': 1, 'driving_lane_id': -1,
            'right_shoulder_lane_id': -2, 'sign_id': '493',
            'sign_text': SIGN_NAME, 'physical_sign_pixels_verified': False,
            'legal_one_way_designation_verified': False, 'official_authority_verified': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
