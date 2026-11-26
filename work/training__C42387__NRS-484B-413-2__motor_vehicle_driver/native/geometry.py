"""Connected right-turn OpenDRIVE proposal for the fixed business cell."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

APPROACH_M = 130.0
LANE_M = 3.5
RADIUS_M = 18.0
STEP_M = 0.1


def route(radius_m: float = RADIUS_M) -> list[list[float]]:
    if radius_m not in (18.0, 22.0):
        raise ValueError('Unplanned right-turn radius')
    points = [[round(-APPROACH_M + i * STEP_M, 6), -LANE_M / 2]
              for i in range(round(APPROACH_M / STEP_M) + 1)]
    center_radius = radius_m - LANE_M / 2
    for i in range(1, math.ceil(math.pi * center_radius / (2 * STEP_M)) + 1):
        angle = min(i * STEP_M / center_radius, math.pi / 2)
        points.append([round(center_radius * math.sin(angle), 6),
                       round(-radius_m + center_radius * math.cos(angle), 6)])
    return points


def open_drive(radius_m: float = RADIUS_M) -> str:
    if radius_m not in (18.0, 22.0):
        raise ValueError('Unplanned right-turn radius')
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C42387-business-right-turn', version='1.00',
                  date='2026-11-25', north='20', south='-30', east='30',
                  west='-140', vendor='worker')
    roads = ((1, -APPROACH_M, 0.0, APPROACH_M, 'line'),
             (2, 0.0, 0.0, math.pi * radius_m / 2, 'arc'))
    for road_id, x, y, length, kind in roads:
        road = ET.SubElement(root, 'road', id=str(road_id),
                             name=f'C42387_business_{road_id}',
                             length=str(length), junction='-1')
        link = ET.SubElement(road, 'link')
        if road_id == 1:
            ET.SubElement(link, 'successor', elementType='road', elementId='2',
                          contactPoint='start')
        else:
            ET.SubElement(link, 'predecessor', elementType='road', elementId='1',
                          contactPoint='end')
        geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                                 s='0', x=str(x), y=str(y), hdg='0',
                                 length=str(length))
        ET.SubElement(geometry, kind,
                      **({'curvature': str(-1 / radius_m)} if kind == 'arc' else {}))
        lanes = ET.SubElement(road, 'lanes')
        ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
        section = ET.SubElement(lanes, 'laneSection', s='0')
        left = ET.SubElement(section, 'left')
        opposing = ET.SubElement(left, 'lane', id='1', type='driving', level='false')
        opposing_link = ET.SubElement(opposing, 'link')
        ET.SubElement(opposing_link, 'predecessor', id='1')
        ET.SubElement(opposing_link, 'successor', id='1')
        ET.SubElement(opposing, 'width', sOffset='0', a=str(LANE_M), b='0', c='0', d='0')
        center = ET.SubElement(section, 'center')
        ET.SubElement(center, 'lane', id='0', type='none', level='false')
        right = ET.SubElement(section, 'right')
        lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
        lane_link = ET.SubElement(lane, 'link')
        ET.SubElement(lane_link, 'predecessor', id='-1')
        ET.SubElement(lane_link, 'successor', id='-1')
        ET.SubElement(lane, 'width', sOffset='0', a=str(LANE_M), b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken', color='white', width='0.12')
        sidewalk = ET.SubElement(right, 'lane', id='-2', type='sidewalk', level='false')
        ET.SubElement(sidewalk, 'width', sOffset='0', a='2', b='0', c='0', d='0')
        ET.SubElement(road, 'objects')
        ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check() -> dict:
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    if len(roads) != 2 or roads[0].find('link/successor').get('elementId') != '2' or \
            roads[1].find('link/predecessor').get('elementId') != '1':
        raise ValueError('Authored Native road connection missing')
    if float(roads[1].find('planView/geometry/arc').get('curvature')) >= 0:
        raise ValueError('Not a right-turn arc')
    points = route()
    gaps = [math.dist(a, b) for a, b in zip(points, points[1:])]
    if max(gaps) >= .101 or math.dist(points[1300], points[1301]) >= .101:
        raise ValueError('Route gap at right-turn connection')
    if points[1300] != [0.0, -LANE_M / 2] or points[-1][1] > -RADIUS_M + 1e-6:
        raise ValueError('Route does not enter right turn')
    if 35 >= APPROACH_M or 20 >= APPROACH_M:
        raise ValueError('Signal interval cannot fit on approach')
    return {'format': 'c42387-connected-right-turn-geometry-v1',
            'authored_route_points': len(points), 'max_step_m': round(max(gaps), 6),
            'approach_m': APPROACH_M, 'right_turn_radius_m': RADIUS_M,
            'unverified': ['Native map lane survey', 'Native body containment',
                           'business-district legal classification', 'physical turn motion']}


if __name__ == '__main__':
    import json
    print(json.dumps(check(), sort_keys=True))
