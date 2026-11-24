"""Signed paved-road draft for the device-directed lamp-use branch."""
import json
import xml.etree.ElementTree as ET

SIGN_NAME = 'HEADLAMPS ON'


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C179824-lamp-device',
                  version='1', date='2026-11-23', north='12', south='-12', east='80', west='-80',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='signed-paved-road', length='160', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                            s='0', x='-80', y='0', hdg='0', length='160')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
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
    ET.SubElement(signals, 'signal', id='100', s='25', t='-6', name=SIGN_NAME,
                  dynamic='no', orientation='+', zOffset='2', country='USA',
                  type='lamp_use_instruction', subtype='headlamps', value='0',
                  unit='none', hOffset='0', pitch='0', roll='0')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    signal = road.find('signals/signal')
    if [(int(x.attrib['id']), x.attrib['type']) for x in lanes] != [
            (-1, 'driving'), (-2, 'shoulder')]:
        raise ValueError('paved road lanes changed')
    if signal is None or signal.attrib['name'] != SIGN_NAME or signal.attrib['orientation'] != '+':
        raise ValueError('lamp-use instruction changed')
    return {'passed': True, 'road_id': 1, 'length_m': 160, 'lane_id': -1,
            'sign_id': '100', 'sign_text': SIGN_NAME,
            'official_authority_verified': False, 'actual_sign_pixels_verified': False,
            'highway_dedication_verified': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
