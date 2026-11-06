"""Authored hill-crest following corridor; Native/public-highway proof pending."""
import json
import math
import xml.etree.ElementTree as ET

ROAD_ID = 1
LANE_ID = -1
LANE_WIDTH_M = 3.5
LANE_Y_M = -1.75
EGO_HALF_LENGTH_M = 2.4
EGO_HALF_WIDTH_M = 1.0
LEAD_HALF_LENGTH_M = 4.5
LEAD_HALF_WIDTH_M = 1.2
EGO_START_X_M = -80.0
SPEED_MPS = 8.0
RATE_HZ = 20
DURATION_S = 45
GAP_TARGET_M = {'condition_a': 10.0, 'condition_b': 25.0}


def elevation(station):
    if station < 50:
        return 0.0
    if station <= 100:
        d = station-50
        return .0048*d*d-.000064*d*d*d
    if station <= 150:
        d = station-100
        return 4-.0048*d*d+.000064*d*d*d
    return 0.0


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C102304-hill-crest-follow-draft', version='1',
                  date='2026-11-06', north='40', south='-40', east='450',
                  west='-150', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id=str(ROAD_ID), name='C102304_follow',
                         length='500', junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='-100', y='0', hdg='0', length='500')
    ET.SubElement(geometry, 'line')
    profile = ET.SubElement(road, 'elevationProfile')
    for station, a, b, c, d in ((0, 0, 0, 0, 0),
                                (50, 0, 0, .0048, -.000064),
                                (100, 4, 0, -.0048, .000064),
                                (150, 0, 0, 0, 0)):
        ET.SubElement(profile, 'elevation', s=str(station), a=str(a),
                      b=str(b), c=str(c), d=str(d))
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    left = ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for side, ident in ((left, 1), (right, -1)):
        lane = ET.SubElement(side, 'lane', id=str(ident), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(LANE_WIDTH_M),
                      b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken',
                      color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def body(center_x, center_y, half_length, half_width):
    return [[center_x-half_length, center_y-half_width],
            [center_x-half_length, center_y+half_width],
            [center_x+half_length, center_y+half_width],
            [center_x+half_length, center_y-half_width]]


def positions(suffix, index):
    if suffix not in GAP_TARGET_M or type(index) is not int or not 0 <= index < RATE_HZ*DURATION_S:
        raise ValueError('Unknown C102304 case or frame')
    ego_x = EGO_START_X_M+SPEED_MPS*(index+1)/RATE_HZ
    lead_x = ego_x+EGO_HALF_LENGTH_M+LEAD_HALF_LENGTH_M+GAP_TARGET_M[suffix]
    return ego_x, lead_x


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    assert road is not None and road.attrib['id'] == '1'
    assert road.find('planView/geometry/line') is not None
    assert len(road.findall('elevationProfile/elevation')) == 4
    assert math.isclose(elevation(50), 0) and math.isclose(elevation(100), 4)
    assert math.isclose(elevation(150), 0, abs_tol=1e-12)
    assert elevation(75) > 0 and elevation(125) > 0
    for suffix in GAP_TARGET_M:
        first = positions(suffix, 0)
        last = positions(suffix, RATE_HZ*DURATION_S-1)
        assert -100 < first[0] < first[1] < 400
        assert -100 < last[0] < last[1] < 400
        assert abs((first[1]-first[0])-EGO_HALF_LENGTH_M-LEAD_HALF_LENGTH_M-
                   GAP_TARGET_M[suffix]) < 1e-9
    return {'road_id': ROAD_ID, 'lane_id': LANE_ID,
            'crest_height_m': 4.0, 'frames': RATE_HZ*DURATION_S,
            'scope': 'authored geometry and commanded positions only; no Native or public-highway proof'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
