"""Authored premises parking bay and neighboring access aisle geometry."""
import xml.etree.ElementTree as ET

AISLE = {'x_min_m': 0.0, 'x_max_m': 7.0, 'y_min_m': -8.0, 'y_max_m': -4.0}
BAY = {'x_min_m': 0.0, 'x_max_m': 7.0, 'y_min_m': -4.0, 'y_max_m': 0.0}
ROUTE = {'x_min_m': 7.0, 'x_max_m': 12.0, 'y_min_m': -8.0, 'y_max_m': -4.0}


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C200542-public-access-premises',
                  version='1', date='2026-11-23', north='30', south='-30', east='60', west='-60', vendor='worker')
    road = ET.SubElement(root, 'road', id='1', name='premises-access-surface', length='120', junction='-1')
    ET.SubElement(road, 'link')
    geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x='-60', y='0', hdg='0', length='120')
    ET.SubElement(geom, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(ET.SubElement(road, 'lanes'), 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center'); ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='10', b='0', c='0', d='0')
    ET.SubElement(road, 'objects'); ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    width = float(root.find('road/lanes/laneSection/right/lane/width').get('a'))
    if width != 10 or AISLE['y_max_m'] != BAY['y_min_m']:
        raise ValueError('Premises aisle/bay geometry differs')
    if AISLE['x_min_m'] != BAY['x_min_m'] or AISLE['x_max_m'] != BAY['x_max_m']:
        raise ValueError('Aisle and accessible bay are no longer paired')
    if ROUTE['x_min_m'] != AISLE['x_max_m'] or ROUTE['y_min_m'] != AISLE['y_min_m'] or ROUTE['y_max_m'] != AISLE['y_max_m']:
        raise ValueError('Aisle and diagnostic accessible route are not contiguous')
    return {'passed': True, 'road_width_m': width, 'access_aisle': AISLE,
            'adjacent_bay': BAY, 'accessible_route_diagnostic_extent': ROUTE,
            'official_designation_proven': False,
            'native_markings_observed': False}
