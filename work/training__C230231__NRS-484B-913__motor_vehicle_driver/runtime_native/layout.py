"""A straight qualifying-way diagnostic with a separately sourced hose crossing."""
import xml.etree.ElementTree as ET

HOSE_LINE = [[0.0, -0.3], [0.0, -6.7]]
HOSE_RADIUS_M = 0.09
WAY_ID = 1


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C230231-hose-way',
                  version='1', date='2026-11-25', north='20', south='-20', east='60', west='-60', vendor='worker')
    road = ET.SubElement(root, 'road', id=str(WAY_ID), name='hose-way', length='120', junction='-1')
    ET.SubElement(road, 'link')
    geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x='-60', y='0', hdg='0', length='120')
    ET.SubElement(geom, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(ET.SubElement(road, 'lanes'), 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='10', b='0', c='0', d='0')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    tree = ET.fromstring(open_drive())
    width = float(tree.find('road/lanes/laneSection/right/lane/width').get('a'))
    if width != 10 or HOSE_LINE[0][0] != HOSE_LINE[1][0] or HOSE_LINE[0][1] <= HOSE_LINE[1][1]:
        raise ValueError('Diagnostic hose/way geometry differs')
    if not (-width < -8.5 - 1 < -8.5 + 1 < 0):
        raise ValueError('Route-around vehicle footprint leaves diagnostic way')
    return {'passed': True, 'way_width_m': width, 'hose_line_xy_m': HOSE_LINE,
            'hose_radius_m': HOSE_RADIUS_M, 'official_way_or_hose_status_proven': False}
