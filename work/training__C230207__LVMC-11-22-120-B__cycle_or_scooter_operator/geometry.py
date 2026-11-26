"""Straight signed roadway and off-road shoulder; no official designation asserted."""
import json
import xml.etree.ElementTree as ET

SIGN_NAME = 'BICYCLES PROHIBITED ON ROADWAY'


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C230207-bicycle-access',
                  version='1', date='2026-11-23', north='20', south='-20', east='60', west='-60',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='signed-straight-road', length='120', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x='-60', y='0', hdg='0', length='120')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', 3.5), (-2, 'shoulder', 2.5)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.1')
    ET.SubElement(road, 'objects')
    signals = ET.SubElement(road, 'signals')
    ET.SubElement(signals, 'signal', id='100', s='15', t='-7', name=SIGN_NAME,
                  dynamic='no', orientation='+', zOffset='2', country='USA',
                  type='bicycle_roadway_prohibition', subtype='bicycle', value='0', unit='none',
                  hOffset='0', pitch='0', roll='0')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    signal = road.find('signals/signal')
    if [l.attrib['type'] for l in lanes] != ['driving', 'shoulder']:
        raise ValueError('roadway and off-road shoulder changed')
    if [float(l.find('width').attrib['a']) for l in lanes] != [3.5, 2.5]:
        raise ValueError('surface widths changed')
    if signal is None or signal.attrib['name'] != SIGN_NAME or signal.attrib['orientation'] != '+':
        raise ValueError('bicycle restriction signal changed')
    return {'passed': True, 'road_id': 1, 'length_m': 120, 'lane_ids': [-1, -2],
            'sign_id': signal.attrib['id'], 'sign_text': SIGN_NAME,
            'sign_s_m': 15, 'governed_direction': 'positive_s',
            'native_sign_pixels_verified': False, 'official_designation_verified': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
