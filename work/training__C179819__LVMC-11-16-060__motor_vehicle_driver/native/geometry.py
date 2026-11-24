"""Long straight paved road for the 30-second speed comparison."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C179819 speed road',
                  version='1.00', date='2026-11-24', north='0', south='0', east='700', west='-100')
    road = ET.SubElement(root, 'road', id='1', name='paved-road', length='800', junction='-1')
    ET.SubElement(road, 'link')
    line = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-100', y='0', hdg='0', length='800')
    ET.SubElement(line, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='4', b='0', c='0', d='0')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    lane = root.find('road/lanes/laneSection/right/lane')
    if road.attrib['length'] != '800' or lane.attrib['type'] != 'driving':
        raise ValueError('speed-road geometry changed')
    return {'road_id': 1, 'length_m': 800, 'lane_id': -1,
            'native_readback_observed': False, 'street_authority_sourced': False}
