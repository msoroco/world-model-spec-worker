"""Authored Fremont sidewalk segment; geographic identity needs local verification."""
import json
import xml.etree.ElementTree as ET

SIGN_NAME = 'NO BICYCLES, ELECTRIC BICYCLES OR ELECTRIC SCOOTERS ON SIDEWALK'


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C230207-Fremont-sidewalk',
                  version='1', date='2026-11-23', north='20', south='-20', east='80', west='-80',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='Fremont Street', length='160', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x='-80', y='0', hdg='0', length='160')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', 3.5), (-2, 'sidewalk', 3.0)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind, level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.1')
    ET.SubElement(road, 'objects')
    signals = ET.SubElement(road, 'signals')
    ET.SubElement(signals, 'signal', id='100', s='25', t='-6.2', name=SIGN_NAME,
                  dynamic='no', orientation='+', zOffset='2', country='USA',
                  type='sidewalk_cycle_prohibition', subtype='bicycle_ebicycle_escooter',
                  value='0', unit='none', hOffset='0', pitch='0', roll='0')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    sign = road.find('signals/signal')
    if road.attrib['name'] != 'Fremont Street' or [l.attrib['type'] for l in lanes] != ['driving', 'sidewalk']:
        raise ValueError('named road or sidewalk geometry changed')
    if [float(l.find('width').attrib['a']) for l in lanes] != [3.5, 3.0]:
        raise ValueError('sidewalk width changed')
    if sign is None or sign.attrib['name'] != SIGN_NAME or sign.attrib['orientation'] != '+':
        raise ValueError('three-class sidewalk restriction sign changed')
    return {'passed': True, 'road_id': 1, 'road_name': road.attrib['name'],
            'length_m': 160, 'lane_ids': [-1, -2], 'sidewalk_lane_id': -2,
            'Main_Street_x_m': -60, 'Seventh_Street_x_m': 60,
            'sign_id': sign.attrib['id'], 'sign_text': SIGN_NAME, 'sign_s_m': 25,
            'geographic_identity_verified': False, 'native_sign_pixels_verified': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
