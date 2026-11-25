"""Paved, open-ended alley-width variants; legal alley status needs sources."""
import argparse
import json
import xml.etree.ElementTree as ET

WIDTHS = {'controlled_1': 7.5, 'controlled_at_10': 6.648, 'controlled_2': 6.0}


def open_drive(width):
    if width not in WIDTHS.values():
        raise ValueError('unknown alley width draft')
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C178965 paved alley draft',
                  version='1.00', date='2026-11-23', north='0', south='0', east='50', west='-50')
    road = ET.SubElement(root, 'road', id='1', name='open-ended paved alley draft', length='100', junction='-1')
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
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
    ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.10')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check(width):
    root = ET.fromstring(open_drive(width))
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    if road.attrib['length'] != '100' or len(lanes) != 1 or lanes[0].attrib != {'id': '-1', 'type': 'driving', 'level': 'false'}:
        raise ValueError('paved alley lane inventory differs')
    measured = float(lanes[0].find('width').attrib['a'])
    if measured != width:
        raise ValueError('alley width differs')
    return {'passed': True, 'road_length_m': 100, 'paved_width_m': width,
            'alley_lateral_edges_m': [-width, 0.0],
            'native_map_readback_observed': False, 'legal_alley_status_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--width', type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.width), sort_keys=True))
