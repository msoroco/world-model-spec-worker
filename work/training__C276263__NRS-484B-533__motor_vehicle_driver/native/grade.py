"""Authored 4% grade and right curb for C276263; slope is engineering only."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C276263-grade',
                  version='1', date='2026-11-23', north='20', south='-20',
                  east='100', west='-100', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='graded-highway-proposal',
                         length='200', junction='-1')
    ET.SubElement(road, 'link')
    geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-100', y='0', hdg='0', length='200')
    ET.SubElement(geom, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='.04', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    road = ET.fromstring(open_drive()).find('road')
    grade = road.find('elevationProfile/elevation')
    lane = road.find('lanes/laneSection/right/lane')
    if (road.attrib['length'] != '200' or float(grade.attrib['b']) != .04 or
            lane.attrib['id'] != '-1' or float(lane.find('width').attrib['a']) != 3.5):
        raise ValueError('Authored grade or curb geometry differs')
    return {'road_id': 1, 'slope_fraction': .04, 'right_curb_y_m': -3.5,
            'native_readback_observed': False, 'perceptibility_reviewed': False}
