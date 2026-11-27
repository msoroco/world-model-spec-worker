"""A single paved lane with an immediately rear vehicle, pending Native review."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C230259 paved road',
                  version='1', date='2026-11-25', north='20', south='-20',
                  east='200', west='-100', vendor='worker')
    road = ET.SubElement(root, 'road', id='1', name='paved one-way road draft',
                         length='300', junction='-1')
    ET.SubElement(road, 'link')
    ET.SubElement(ET.SubElement(road, 'type', s='0', type='rural'),
                  'speed', max='35', unit='mph')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='-100', y='0', hdg='0', length='300')
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(ET.SubElement(road, 'lanes'), 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    ET.SubElement(lane, 'roadMark', sOffset='0', type='broken', color='white', width='0.15')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    lanes = root.findall('road/lanes/laneSection/right/lane')
    if len(roads) != 1 or roads[0].get('length') != '300' or len(lanes) != 1:
        raise ValueError('Original paved lane geometry differs')
    if lanes[0].get('id') != '-1' or lanes[0].get('type') != 'driving':
        raise ValueError('Required shared driving lane absent')
    return {'passed': True, 'lane_id': -1, 'public_highway_authority_reviewed': False}
