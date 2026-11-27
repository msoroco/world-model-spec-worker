"""Unselected right-turn OpenDRIVE proposal from the frozen straight source.

This builds geometry for a later authorized turn binding. It does not change the
selected C111071 straight scene or assert CARLA import or physical acceptance.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
ASSIGNMENT = PACKAGE.name
SOURCE = HERE / 'authored-road.xodr'
FROZEN = ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'
CATALOG = ROOT / 'inputs' / 'coverage' / 'candidate-cells.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_check():
    assignment = json.loads(FROZEN.read_text())
    catalog = json.loads(CATALOG.read_text())
    if (assignment['law_id'], assignment['actor'], assignment['cell']['maneuver']) != (
            'NRS-484B-307-9b', 'motorcycle_or_moped_operator', 'straight'):
        raise ValueError('Frozen source identity differs')
    if 'turn in the direction opposite' not in assignment['law']['text']:
        raise ValueError('Opposite-turn statutory alternative absent')
    eligible = [cell['cell_id'] for cell in catalog['cells']
                if cell['layout'] == 'intersection'
                and cell['control'] == 'inoperative_signal'
                and cell['maneuver'] == 'right_turn'
                and assignment['actor'] in cell['candidate_ego_parties']]
    if eligible:
        raise ValueError('Actor-eligible turn cell exists; review binding first')
    root = ET.parse(SOURCE).getroot()
    road1 = root.find("road[@id='1']")
    road2 = root.find("road[@id='2']")
    arrow = road1.find("signals/signal[@id='602']")
    if arrow is None or arrow.get('name') != 'ego-green-left-arrow':
        raise ValueError('Original source green-left arrow absent')
    if road1.find('planView/geometry').get('hdg') != str(math.pi / 2):
        raise ValueError('Source approach direction differs')
    if road2.find('planView/geometry').get('hdg') != '0':
        raise ValueError('Source right exit direction differs')
    if root.find("junction/connection[@incomingRoad='1'][@connectingRoad='13']") is None:
        raise ValueError('Original straight connector absent')
    return root, {'assignment_sha256': digest(FROZEN),
                  'catalog_sha256': digest(CATALOG), 'straight_map_sha256': digest(SOURCE),
                  'actor_eligible_right_turn_cell_ids': eligible}


def construct():
    root, binding = source_check()
    connector = ET.Element('road', {'id': '15', 'name': 'C111071_conditional_right_turn_15',
                                     'length': str(7 * math.pi / 2), 'junction': '100'})
    link = ET.SubElement(connector, 'link')
    ET.SubElement(link, 'predecessor', {'elementType': 'road', 'elementId': '1', 'contactPoint': 'end'})
    ET.SubElement(link, 'successor', {'elementType': 'road', 'elementId': '2', 'contactPoint': 'start'})
    plan = ET.SubElement(connector, 'planView')
    geometry = ET.SubElement(plan, 'geometry', {'s': '0', 'x': '0', 'y': '-7',
                                                'hdg': str(math.pi / 2),
                                                'length': str(7 * math.pi / 2)})
    ET.SubElement(geometry, 'arc', {'curvature': str(-1 / 7)})
    ET.SubElement(ET.SubElement(connector, 'elevationProfile'), 'elevation',
                  {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    lanes = ET.SubElement(connector, 'lanes')
    ET.SubElement(lanes, 'laneOffset', {'s': '0', 'a': '0', 'b': '0', 'c': '0', 'd': '0'})
    section = ET.SubElement(lanes, 'laneSection', {'s': '0'})
    left = ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    right = ET.SubElement(section, 'right')
    for parent, lid, typ in ((left, '1', 'driving'), (center, '0', 'none'),
                             (right, '-1', 'driving')):
        lane = ET.SubElement(parent, 'lane', {'id': lid, 'type': typ, 'level': 'false'})
        if lid != '0':
            ET.SubElement(lane, 'width', {'sOffset': '0', 'a': '3.5', 'b': '0', 'c': '0', 'd': '0'})
            lane_link = ET.SubElement(lane, 'link')
            ET.SubElement(lane_link, 'predecessor', {'id': lid})
            ET.SubElement(lane_link, 'successor', {'id': lid})
        ET.SubElement(lane, 'roadMark', {'sOffset': '0', 'type': 'broken' if lid != '0' else 'solid',
                                        'color': 'white' if lid != '0' else 'yellow', 'width': '0.12'})
    ET.SubElement(connector, 'objects')
    ET.SubElement(connector, 'signals')
    junction = root.find('junction')
    root.insert(list(root).index(junction), connector)
    connection = ET.SubElement(junction, 'connection',
                               {'id': '3', 'incomingRoad': '1', 'connectingRoad': '15',
                                'contactPoint': 'start'})
    ET.SubElement(connection, 'laneLink', {'from': '-1', 'to': '-1'})
    data = ET.tostring(root, encoding='utf-8') + b'\n'
    inspect(data)
    return data, binding


def inspect(data):
    root = ET.fromstring(data)
    connector = root.find("road[@id='15']")
    connection = root.find("junction/connection[@incomingRoad='1'][@connectingRoad='15']")
    if connector is None or connection is None or connection.find('laneLink').attrib != {'from': '-1', 'to': '-1'}:
        raise ValueError('Conditional junction lane connection absent')
    geometry = connector.find('planView/geometry')
    if geometry is None or geometry.find('arc') is None:
        raise ValueError('Conditional turn arc absent')
    length = float(geometry.get('length'))
    curvature = float(geometry.find('arc').get('curvature'))
    heading = float(geometry.get('hdg'))
    start_x, start_y = float(geometry.get('x')), float(geometry.get('y'))
    end_heading = heading + curvature * length
    end_x = start_x + (math.sin(end_heading) - math.sin(heading)) / curvature
    end_y = start_y - (math.cos(end_heading) - math.cos(heading)) / curvature
    exit_geometry = root.find("road[@id='2']/planView/geometry")
    if (abs(end_x - float(exit_geometry.get('x'))) > 1e-6 or
            abs(end_y - float(exit_geometry.get('y'))) > 1e-6 or
            abs(end_heading - float(exit_geometry.get('hdg'))) > 1e-6):
        raise ValueError('Conditional turn misses source eastbound exit')
    if not math.isclose(curvature, -1 / 7) or not math.isclose(length, 7 * math.pi / 2):
        raise ValueError('Conditional turn radius or direction differs')
    if connector.find("lanes/laneSection/right/lane[@id='-1']/link/successor[@id='-1']") is None:
        raise ValueError('Conditional lane successor absent')
    return {'start_m': [start_x, start_y], 'end_m': [end_x, end_y],
            'start_heading_rad': heading, 'end_heading_rad': end_heading,
            'radius_m': 7, 'turn': 'right'}


def proof():
    data, binding = construct()
    geometry = inspect(data)
    negatives = 0
    for old, new in ((b'curvature="-0.14285714285714285"', b'curvature="0.14285714285714285"'),
                     (b'connectingRoad="15"', b'connectingRoad="13"')):
        if old not in data:
            raise ValueError('Expected mutation target absent')
        try:
            inspect(data.replace(old, new, 1))
        except ValueError:
            negatives += 1
        else:
            raise AssertionError('Mutated turn proposal was accepted: ' + old.decode())
    bad_root = ET.fromstring(data)
    bad_root.find("road[@id='15']/lanes/laneSection/right/lane[@id='-1']/link/successor").set('id', '1')
    try:
        inspect(ET.tostring(bad_root, encoding='utf-8'))
    except ValueError:
        negatives += 1
    else:
        raise AssertionError('Mutated turn lane successor was accepted')
    return data, {'format': 'c111071-conditional-right-turn-geometry-v1',
                  'selected': False, 'physical_import_verified': False,
                  'eligible_binding_verified': False, 'map_sha256': hashlib.sha256(data).hexdigest(),
                  'binding': binding, 'geometry': geometry, 'controlled_negatives_rejected': negatives}


if __name__ == '__main__':
    data, receipt = proof()
    target = PACKAGE / 'conditional-turn'
    target.mkdir(exist_ok=True)
    (target / 'authored-right-turn.xodr').write_bytes(data)
    (target / 'geometry-proof.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))
