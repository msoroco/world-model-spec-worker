"""Authored bridge approach; original Native deck and support remain to be reviewed."""
import xml.etree.ElementTree as ET

BRIDGE_START_M = 0.0
BRIDGE_END_M = 100.0
DECK_HEIGHT_M = 8.0
LANE_CENTER_Y_M = -1.75
DECK_POLYGON_XY_M = [[0.0, -3.5], [100.0, -3.5], [100.0, 0.0], [0.0, 0.0]]


def elevation(x):
    if x < -50.0:
        return 0.0
    if x < 0.0:
        return (x + 50.0) * DECK_HEIGHT_M / 50.0
    if x <= BRIDGE_END_M:
        return DECK_HEIGHT_M
    if x <= 150.0:
        return (150.0 - x) * DECK_HEIGHT_M / 50.0
    return 0.0


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C31675 bridge approach', version='1.00', date='2026-11-27',
                  north='0', south='0', east='200', west='-100')
    road = ET.SubElement(root, 'road', id='1', name='bridge-approach',
                         length='300', junction='-1')
    ET.SubElement(road, 'link')
    geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                         s='0', x='-100', y='0', hdg='0', length='300')
    ET.SubElement(geom, 'line')
    profile = ET.SubElement(road, 'elevationProfile')
    for s, a, b in ((0, 0, 0), (50, 0, .16), (100, 8, 0),
                    (200, 8, -.16), (250, 0, 0)):
        ET.SubElement(profile, 'elevation', s=str(s), a=str(a),
                      b=str(b), c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    lane = ET.SubElement(left, 'lane', id='1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
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
    elevations = root.findall('road/elevationProfile/elevation')
    if len(elevations) != 5 or [float(v.get('s')) for v in elevations] != [0, 50, 100, 200, 250]:
        raise ValueError('bridge elevation profile changed')
    if [int(v.get('id')) for v in root.findall('road/lanes/laneSection/right/lane')] != [-1]:
        raise ValueError('bridge travel lane changed')
    if not (elevation(-75) == 0 and elevation(0) == 8 and elevation(50) == 8
            and elevation(100) == 8 and elevation(175) == 0):
        raise ValueError('bridge support geometry changed')
    return {'road_id': 1, 'lane_id': -1, 'lane_center_y_m': LANE_CENTER_Y_M,
            'deck_polygon_xy_m': DECK_POLYGON_XY_M, 'elevation_m': DECK_HEIGHT_M,
            'native_readback_observed': False, 'physical_support_verified': False}
