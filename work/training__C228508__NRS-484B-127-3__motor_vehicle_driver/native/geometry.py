"""Straight two-lane same-direction road for a moving caravan and entrant."""

import xml.etree.ElementTree as ET

ROAD_ID = 1
CARAVAN_LANE_ID = -1
ENTRANT_LANE_ID = -2
CARAVAN_Y_M = -1.75
ENTRANT_Y_M = -5.25
ROAD_LENGTH_M = 420.0


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C228508-caravan-draft',
                  version='1', date='2026-11-27', north='30', south='-30',
                  east='420', west='0', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id=str(ROAD_ID), name='caravan_corridor',
                         length=str(ROAD_LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='0', y='0', hdg='0', length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, 'line')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for ident in (CARAVAN_LANE_ID, ENTRANT_LANE_ID):
        lane = ET.SubElement(right, 'lane', id=str(ident), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken', color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    road = root.find('road')
    assert road.attrib['id'] == str(ROAD_ID)
    assert road.find('planView/geometry/line') is not None
    right = road.find('lanes/laneSection/right')
    assert {int(l.attrib['id']) for l in right.findall('lane')} == {-1, -2}
    assert 0 > CARAVAN_Y_M > ENTRANT_Y_M
    return {'road_id': ROAD_ID, 'same_direction_lane_ids': [-1, -2],
            'authored_road_length_m': ROAD_LENGTH_M,
            'public_highway_status_verified': False,
            'outside_business_district_verified': False}
