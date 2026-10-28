"""Authored geometry and routes for the partition-02 capability experiments."""
import math
import xml.etree.ElementTree as ET


def road(root, ident, x, y, heading, length, lanes=2, junction='-1', curvature=None,
         left_driving=True):
    item = ET.SubElement(root, 'road', {'name': f'road_{ident}', 'id': str(ident),
                                        'length': str(length), 'junction': str(junction)})
    ET.SubElement(item, 'link')
    view = ET.SubElement(item, 'planView')
    geometry = ET.SubElement(view, 'geometry', {'s': '0', 'x': str(x), 'y': str(y),
        'hdg': str(heading), 'length': str(length)})
    ET.SubElement(geometry, 'line' if curvature is None else 'arc',
                  {} if curvature is None else {'curvature': str(curvature)})
    elevation = ET.SubElement(item, 'elevationProfile')
    ET.SubElement(elevation, 'elevation', {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    lanes_element = ET.SubElement(item, 'lanes')
    ET.SubElement(lanes_element, 'laneOffset', {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    section = ET.SubElement(lanes_element, 'laneSection', {'s': '0'})
    for side, lane_ids in (('left', range(1, lanes + 1) if left_driving else ()),
                           ('right', range(-1, -lanes - 1, -1))):
        bank = ET.SubElement(section, side)
        for lane_id in lane_ids:
            lane = ET.SubElement(bank, 'lane', {'id': str(lane_id), 'type': 'driving', 'level': 'false'})
            ET.SubElement(lane, 'link')
            ET.SubElement(lane, 'width', {'sOffset': '0', 'a': '3.5', 'b': '0', 'c': '0', 'd': '0'})
            ET.SubElement(lane, 'roadMark', {'sOffset': '0', 'type': 'broken' if abs(lane_id) == 1 else 'solid',
                'weight': 'standard', 'color': 'white', 'width': '.12', 'laneChange': 'both'})
    centre = ET.SubElement(section, 'center')
    centre_lane = ET.SubElement(centre, 'lane', {'id': '0', 'type': 'none', 'level': 'false'})
    ET.SubElement(centre_lane, 'roadMark', {'sOffset': '0', 'type': 'solid', 'weight': 'standard',
        'color': 'yellow', 'width': '.12', 'laneChange': 'none'})
    return item


def build_xodr(mode):
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', {'revMajor': '1', 'revMinor': '4', 'name': f'partition02_{mode}',
        'version': '1', 'date': '2026-10-28', 'north': '500', 'south': '-100',
        'east': '500', 'west': '-100', 'vendor': 'worker-demo-test-first-run-v3'})
    if mode == 'crossing_priority':
        # Two separate carriageway crossings at y=-8 and y=+8. Their centres
        # are 16 m apart, above the supplied 30 ft separate-intersection rule.
        road(root, 1, -80, -8, 0, 73)
        road(root, 2, 7, -8, 0, 73)
        road(root, 3, 80, 8, math.pi, 73)
        road(root, 4, -7, 8, math.pi, 73)
        road(root, 5, 0, -80, math.pi / 2, 65)
        road(root, 6, 0, -1, math.pi / 2, 2)
        road(root, 7, 0, 15, math.pi / 2, 65)
        road(root, 11, -7, -8, 0, 14, junction='101')
        road(root, 12, 0, -15, math.pi / 2, 14, junction='101')
        road(root, 13, 7, 8, math.pi, 14, junction='102')
        road(root, 14, 0, 1, math.pi / 2, 14, junction='102')
        for jid, connections in [(101, [(1, 11), (5, 12)]),
                                 (102, [(3, 13), (6, 14)])]:
            junction = ET.SubElement(root, 'junction', {'id': str(jid), 'name': f'roadway_crossing_{jid}'})
            for index, (incoming, connector) in enumerate(connections):
                connection = ET.SubElement(junction, 'connection', {'id': str(index),
                    'incomingRoad': str(incoming), 'connectingRoad': str(connector), 'contactPoint': 'start'})
                for lane_id in (-1, -2, 1, 2):
                    ET.SubElement(connection, 'laneLink', {'from': str(lane_id), 'to': str(lane_id)})
    elif mode == 'signal':
        approach = road(root, 1, -80, 0, 0, 73)
        road(root, 2, 7, 0, 0, 73)
        road(root, 3, 0, 7, math.pi / 2, 73)
        road(root, 4, 0, -80, math.pi / 2, 73)
        connector = road(root, 13, -7, 0, 0, 7 * math.pi / 2,
                         junction='100', curvature=-1 / 7)
        ET.SubElement(approach.find('link'), 'successor', {'elementType': 'junction', 'elementId': '100'})
        ET.SubElement(connector.find('link'), 'predecessor', {'elementType': 'road', 'elementId': '1'})
        junction = ET.SubElement(root, 'junction', {'id': '100', 'name': 'crossing_highways'})
        connection = ET.SubElement(junction, 'connection', {'id': '0', 'incomingRoad': '1',
            'connectingRoad': '13', 'contactPoint': 'start'})
        for lane_id in (-1, -2, 1, 2):
            ET.SubElement(connection, 'laneLink', {'from': str(lane_id), 'to': str(lane_id)})
    elif mode == 'divider_turn':
        road(root, 1, -80, -8, 0, 160)
        road(root, 2, 80, 8, math.pi, 160)
        turn = road(root, 13, -10, -8, 0, 8 * math.pi,
                    junction='100', curvature=1 / 8)
        junction = ET.SubElement(root, 'junction', {'id': '100', 'name': 'median_opening'})
        connection = ET.SubElement(junction, 'connection', {'id': '0', 'incomingRoad': '1',
            'connectingRoad': '13', 'contactPoint': 'start'})
        ET.SubElement(connection, 'laneLink', {'from': '-1', 'to': '-1'})
        ET.SubElement(turn.find('link'), 'predecessor', {'elementType': 'road', 'elementId': '1'})
    elif mode == 'speed':
        road(root, 1, 0, 0, 0, 500)
    elif mode == 'oneway':
        road(root, 1, -80, 0, 0, 160, left_driving=False)
    else:
        raise ValueError('Unsupported authored scene mode: ' + mode)
    return ET.tostring(root, encoding='unicode') + '\n'


def route(mode, case, other=False):
    if mode == 'crossing_priority':
        if other:
            return [(1.75, -70 + i * .5) for i in range(281)]
        return [(-70 + i * .5, -9.75) for i in range(281)]
    if mode == 'divider_turn':
        kind = case['variable_assignments']['path_kind']['value']
        centre = -35 if kind == 'divider_crossing' else -10
        approach = [(-70 + (centre + 70) * i / 120, -9.75) for i in range(121)]
        arc = [(centre + 9.75 * math.sin(math.pi * i / 80),
                -9.75 + 9.75 * (1 - math.cos(math.pi * i / 80))) for i in range(1, 81)]
        depart = [(centre - i * .5, 9.75) for i in range(1, 121)]
        return approach + arc + depart
    if mode == 'oneway':
        direction = case['variable_assignments']['direction']['value']
        return [(-70 + i * .5, -1.75) for i in range(281)] if direction == 'designated' else [
            (70 - i * .5, -1.75) for i in range(281)]
    if mode == 'speed':
        return [(i * .5, -1.75 if not other else -5.25) for i in range(801)]
    if mode == 'signal':
        approach = [(-70 + i * .5, -1.75) for i in range(121)]
        arc = [(-10 + 8 * math.sin(math.pi * i / 160),
                -1.75 - 8 * (1 - math.cos(math.pi * i / 160))) for i in range(1, 81)]
        depart = [(-2, -9.75 - i * .5) for i in range(1, 121)]
        return approach + arc + depart
    raise ValueError('Unsupported route mode: ' + mode)
