"""Authored parallel frontage/highway geometry for the entry comparison.

Road labels and the gate marker are construction requests, not proof of an
official controlled-access designation or an indicated legal entrance.
"""
import xml.etree.ElementTree as ET

HIGHWAY_EDGE_Y_M = -3.5
INDICATED_GATE_X_M = 0.0


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C228131 entry draft',
                  version='1', date='2026-11-23', north='12', south='-20',
                  east='100', west='-100', vendor='worker')
    for road_id, name, y, kind in ((1, 'highway draft', 0, 'motorway'),
                                   (2, 'frontage road draft', -9, 'town')):
        road = ET.SubElement(root, 'road', id=str(road_id), name=name,
                             length='200', junction='-1')
        ET.SubElement(road, 'link')
        ET.SubElement(road, 'type', s='0', type=kind)
        geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                                 s='0', x='-100', y=str(y), hdg='0', length='200')
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
        ET.SubElement(road, 'objects')
        ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    if [(r.get('id'), r.get('length')) for r in roads] != [('1', '200'), ('2', '200')]:
        raise ValueError('Parallel road geometry differs')
    if [r.find('type').get('type') for r in roads] != ['motorway', 'town']:
        raise ValueError('Road type requests differ')
    if [float(r.find('planView/geometry').get('y')) for r in roads] != [0, -9]:
        raise ValueError('Road centerlines differ')
    return {'road_ids': [1, 2], 'edge_y_m': HIGHWAY_EDGE_Y_M,
            'gate_x_m': INDICATED_GATE_X_M,
            'junction_or_designated_entrance_constructed': False,
            'legal_designation_or_device_authority_verified': False}
