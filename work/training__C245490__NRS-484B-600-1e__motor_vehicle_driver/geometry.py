"""Long same-direction two-lane road for the 80 mph comparison."""
import json
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C245490-two-lane-speed',
                  version='1', date='2026-11-23', north='30', south='-30', east='850', west='-850',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='same-direction-two-lane', length='1700', junction='-1')
    ET.SubElement(road, 'link')
    segment = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                            s='0', x='-850', y='0', hdg='0', length='1700')
    ET.SubElement(segment, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id in (-1, -2):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken' if lane_id == -1 else 'solid',
                      color='white', width='.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    if road.attrib['length'] != '1700' or [int(l.attrib['id']) for l in lanes] != [-1, -2]:
        raise ValueError('same-direction road length/lane inventory changed')
    if [float(l.find('width').attrib['a']) for l in lanes] != [3.5, 3.5]:
        raise ValueError('lane widths changed')
    return {'passed': True, 'road_length_m': 1700, 'lane_ids': [-1, -2],
            'lane_widths_m': [3.5, 3.5], 'native_lane_readback_observed': False,
            'high_speed_lane_change_observed': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
