"""CPU-authored split and rejoin road; legal access status needs independent evidence.

Road 1 approaches the choice, roads 2 and 3 join road 4 at the same
destination. Road 3 is the longer alternate route. The no-route comparison
omits road 3 but preserves all mainline geometry.
"""
import json
import math
import xml.etree.ElementTree as ET

RADIUS = 20.0
QUARTER = math.pi * RADIUS / 2
ALTERNATE_LENGTH = 4 * QUARTER + 70.0


def _road(root, number, name, length, x, y, heading, junction, predecessor=None,
          successor=None, segments=None):
    road = ET.SubElement(root, 'road', id=str(number), name=name,
                         length=str(length), junction=str(junction))
    link = ET.SubElement(road, 'link')
    if predecessor is not None:
        ET.SubElement(link, 'predecessor', elementType=predecessor[0],
                      elementId=str(predecessor[1]), contactPoint='end')
    if successor is not None:
        ET.SubElement(link, 'successor', elementType=successor[0],
                      elementId=str(successor[1]), contactPoint='start')
    view = ET.SubElement(road, 'planView')
    if segments is None:
        segments = [(length, 0)]
    s = 0.0
    for segment_length, curvature in segments:
        geometry = ET.SubElement(view, 'geometry', s=str(s), x=str(x), y=str(y),
                                 hdg=str(heading), length=str(segment_length))
        if curvature:
            ET.SubElement(geometry, 'arc', curvature=str(curvature))
            delta = curvature * segment_length
            x += (math.sin(heading + delta) - math.sin(heading)) / curvature
            y += (-math.cos(heading + delta) + math.cos(heading)) / curvature
            heading += delta
        else:
            ET.SubElement(geometry, 'line')
            x += segment_length * math.cos(heading)
            y += segment_length * math.sin(heading)
        s += segment_length
    elevation = ET.SubElement(road, 'elevationProfile')
    ET.SubElement(elevation, 'elevation', s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    lane = ET.SubElement(right, 'lane', id='-1', type='driving', level='false')
    ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
    lane_link = ET.SubElement(lane, 'link')
    if predecessor is not None:
        ET.SubElement(lane_link, 'predecessor', id='-1')
    if successor is not None:
        ET.SubElement(lane_link, 'successor', id='-1')
    ET.SubElement(lane, 'roadMark', sOffset='0', type='broken', color='white', width='.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return x, y, heading


def open_drive(alternate_possible=True):
    if type(alternate_possible) is not bool:
        raise ValueError('alternate route selection must be boolean')
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C230259-split-rejoin-draft', version='1', date='2026-11-26',
                  north='20', south='-60', east='260', west='-110',
                  vendor='full-train-worker')
    _road(root, 1, 'controlled-access-approach', 100, -100, 0, 0, -1,
          successor=('junction', 100))
    _road(root, 2, 'mainline-through-connection', 150, 0, 0, 0, 100,
          predecessor=('road', 1), successor=('road', 4))
    if alternate_possible:
        _road(root, 3, 'alternate-connected-route', ALTERNATE_LENGTH,
              0, 0, 0, 100, predecessor=('road', 1), successor=('road', 4),
              segments=[(QUARTER, -1 / RADIUS), (QUARTER, 1 / RADIUS),
                        (70, 0), (QUARTER, 1 / RADIUS), (QUARTER, -1 / RADIUS)])
    _road(root, 4, 'shared-journey-destination', 100, 150, 0, 0, -1,
          predecessor=('junction', 100))
    junction = ET.SubElement(root, 'junction', id='100', name='route-choice')
    for index, road_id in enumerate((2, 3) if alternate_possible else (2,)):
        connection = ET.SubElement(junction, 'connection', id=str(index),
                                   incomingRoad='1', connectingRoad=str(road_id),
                                   contactPoint='start')
        ET.SubElement(connection, 'laneLink', **{'from': '-1', 'to': '-1'})
    return ET.tostring(root, encoding='unicode')


def check(alternate_possible=True):
    root = ET.fromstring(open_drive(alternate_possible))
    roads = {int(r.get('id')): r for r in root.findall('road')}
    expected = {1, 2, 3, 4} if alternate_possible else {1, 2, 4}
    if set(roads) != expected:
        raise ValueError('exact split/rejoin roads differ')
    links = [(int(c.get('incomingRoad')), int(c.get('connectingRoad')))
             for c in root.findall('junction/connection')]
    if links != ([(1, 2), (1, 3)] if alternate_possible else [(1, 2)]):
        raise ValueError('junction lane connections differ')
    for road in roads.values():
        lane = road.find('lanes/laneSection/right/lane')
        if lane is None or lane.get('id') != '-1' or lane.get('type') != 'driving':
            raise ValueError('driving lane missing')
    x, y, heading = _trace_endpoint(root, 3) if alternate_possible else (150, 0, 0)
    if max(abs(x - 150), abs(y), abs(heading)) > 1e-8:
        raise ValueError('alternate geometry does not rejoin destination')
    return {'passed': True, 'road_ids': sorted(roads), 'junction_links': links,
            'same_destination_road_id': 4, 'alternate_possible_in_authored_map':
            alternate_possible, 'controlled_access_legally_verified': False,
            'native_topology_verified': False}


def _trace_endpoint(root, road_id):
    segments = root.find(f"road[@id='{road_id}']/planView").findall('geometry')
    last = segments[-1]
    x, y, heading, length = (float(last.get(k)) for k in ('x', 'y', 'hdg', 'length'))
    curvature = float(last.find('arc').get('curvature')) if last.find('arc') is not None else 0
    if curvature:
        delta = curvature * length
        x += (math.sin(heading + delta) - math.sin(heading)) / curvature
        y += (-math.cos(heading + delta) + math.cos(heading)) / curvature
        heading += delta
    else:
        x += length * math.cos(heading)
        y += length * math.sin(heading)
    return x, y, heading


if __name__ == '__main__':
    print(json.dumps([check(True), check(False)], sort_keys=True))
