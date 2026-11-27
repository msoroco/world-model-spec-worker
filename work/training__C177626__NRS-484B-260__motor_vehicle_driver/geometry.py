"""Authored private-way approach crossing a two-way paved highway."""
import math
import xml.etree.ElementTree as ET

HIGHWAY_ROAD = 1
PRIVATE_ROAD = 2
CONFLICT_X_M = 2.0
HIGHWAY_Y_M = -2.0
PRIVATE_X_M = 2.0


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C177626-private-entry',
                  version='1', date='2026-11-26', north='40', south='-40',
                  east='260', west='-110', vendor='full-train-worker')
    for road_id, x, y, heading, length, width, two_way in (
        (HIGHWAY_ROAD, -100, 0, 0, 350, 4.0, True),
        (PRIVATE_ROAD, 0, -40, math.pi / 2, 36, 4.0, False),
    ):
        road = ET.SubElement(root, 'road', id=str(road_id), name=f'C177626_{road_id}',
                             length=str(length), junction='-1')
        ET.SubElement(road, 'link')
        geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                                 s='0', x=str(x), y=str(y), hdg=str(heading), length=str(length))
        ET.SubElement(geometry, 'line')
        ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                      s='0', a='0', b='0', c='0', d='0')
        lanes = ET.SubElement(road, 'lanes')
        ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
        section = ET.SubElement(lanes, 'laneSection', s='0')
        for side, ids in (('left', (1,) if two_way else ()), ('center', (0,)), ('right', (-1,))):
            group = ET.SubElement(section, side)
            for lane_id in ids:
                lane = ET.SubElement(group, 'lane', id=str(lane_id),
                                     type='none' if lane_id == 0 else 'driving', level='false')
                if lane_id:
                    ET.SubElement(lane, 'width', sOffset='0', a=str(width), b='0', c='0', d='0')
                ET.SubElement(lane, 'roadMark', sOffset='0', type='solid' if lane_id == 0 else 'broken',
                              color='yellow' if lane_id == 0 else 'white', width='0.12')
        ET.SubElement(road, 'objects')
        ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check():
    root = ET.fromstring(open_drive())
    roads = {int(road.attrib['id']): road for road in root.findall('road')}
    if set(roads) != {HIGHWAY_ROAD, PRIVATE_ROAD}:
        raise ValueError('Required highway and private way absent')
    if not (-4 < HIGHWAY_Y_M < 0 and 0 < PRIVATE_X_M < 4):
        raise ValueError('Planned lane centers differ')
    if not all(road.find('planView/geometry/line') is not None for road in roads.values()):
        raise ValueError('Source road axes absent')
    return {'road_ids': sorted(roads), 'conflict_xy_m': [CONFLICT_X_M, HIGHWAY_Y_M],
            'source': 'authored geometry; Native road and lane readback required'}
