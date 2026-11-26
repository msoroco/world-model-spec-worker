"""Authored one-way two-lane straight passing road for the electric bicycle."""
import math
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C146108-one-way-pass',
                  version='1', date='2026-11-26', north='30', south='-30', east='300', west='-100',
                  vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='one-way-two-lane', length='400', junction='-1')
    ET.SubElement(road, 'link')
    geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x='-100', y='0', hdg='0', length='400')
    ET.SubElement(geom, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    lane = ET.SubElement(center, 'lane', id='0', type='none', level='false')
    ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='yellow', width='0.12')
    right = ET.SubElement(section, 'right')
    for lane_id in (-1, -2):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken' if lane_id == -1 else 'solid',
                      color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lanes = road.findall('lanes/laneSection/right/lane')
    if road.attrib['length'] != '400' or [int(l.attrib['id']) for l in lanes] != [-1, -2]:
        raise ValueError('One-way two-lane source geometry differs')
    if root.findall('.//junction') or root.findall('.//signal'):
        raise ValueError('Uncontrolled straight passing road changed')
    widths = [float(l.find('width').attrib['a']) for l in lanes]
    if widths != [3.5, 3.5] or not all(math.isfinite(v) for v in widths):
        raise ValueError('Lane widths differ')
    return {'passed': True, 'road_length_m': 400, 'through_lanes': [-1, -2],
            'lane_widths_m': widths, 'native_map_readback_observed': False,
            'physical_pass_observed': False}
