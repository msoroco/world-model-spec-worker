"""Two clearly marked same-direction lanes for the textual CPU fixture."""
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C245490 two marked lanes fixture', version='1',
                  date='2026-11-25', north='20', south='-20',
                  east='200', west='-100', vendor='worker')
    road = ET.SubElement(root, 'road', id='1',
                         name='two same-direction lanes fixture',
                         length='300', junction='-1')
    ET.SubElement(road, 'link')
    ET.SubElement(ET.SubElement(road, 'type', s='0', type='rural'),
                  'speed', max='35', unit='mph')
    geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-100', y='0', hdg='0', length='300')
    ET.SubElement(geom, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(ET.SubElement(road, 'lanes'), 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, mark in [(-1, 'broken'), (-2, 'solid')]:
        lane = ET.SubElement(right, 'lane', id=str(lane_id),
                             type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type=mark,
                      color='white', width='0.15')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    lanes = root.findall('road/lanes/laneSection/right/lane')
    if len(lanes) != 2 or [lane.get('id') for lane in lanes] != ['-1', '-2']:
        raise ValueError('Fixture lacks two same-direction lanes')
    if any(lane.get('type') != 'driving' for lane in lanes):
        raise ValueError('Fixture target is not a driving lane')
    return {'passed': True, 'lane_ids': [-1, -2],
            'physical_map_authority_reviewed': False}
