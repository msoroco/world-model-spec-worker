"""Two-lane large-radius roundabout arc joined to an exit tangent."""
import json
import math
import xml.etree.ElementTree as ET

RADIUS_M = 500.0
ARC_M = RADIUS_M * math.pi / 2
EXIT_M = 1200.0

def _lanes(road):
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    center = ET.SubElement(section, 'center')
    ET.SubElement(center, 'lane', id='0', type='none', level='false')
    right = ET.SubElement(section, 'right')
    for ident in (-1, -2):
        lane = ET.SubElement(right, 'lane', id=str(ident), type='driving', level='false')
        link = ET.SubElement(lane, 'link')
        ET.SubElement(link, 'predecessor', id=str(ident))
        ET.SubElement(link, 'successor', id=str(ident))
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken' if ident == -1 else 'solid', color='white', width='.12')

def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C131055-multilane-roundabout-exit', version='1', date='2026-11-23', north='100', south='-600', east='1300', west='-600', vendor='full-train-worker')
    arc = ET.SubElement(root, 'road', id='1', name='two-lane-roundabout-arc', length=f'{ARC_M:.9f}', junction='-1')
    link = ET.SubElement(arc, 'link')
    ET.SubElement(link, 'successor', elementType='road', elementId='2', contactPoint='start')
    geom = ET.SubElement(ET.SubElement(arc, 'planView'), 'geometry', s='0', x='-500', y='0', hdg=f'{-math.pi/2:.9f}', length=f'{ARC_M:.9f}')
    ET.SubElement(geom, 'arc', curvature=f'{1/RADIUS_M:.9f}')
    _lanes(arc)
    ET.SubElement(arc, 'objects')
    ET.SubElement(arc, 'signals')
    exit_road = ET.SubElement(root, 'road', id='2', name='roundabout-east-exit', length=str(EXIT_M), junction='-1')
    link = ET.SubElement(exit_road, 'link')
    ET.SubElement(link, 'predecessor', elementType='road', elementId='1', contactPoint='end')
    geom = ET.SubElement(ET.SubElement(exit_road, 'planView'), 'geometry', s='0', x='0', y='-500', hdg='0', length=str(EXIT_M))
    ET.SubElement(geom, 'line')
    _lanes(exit_road)
    ET.SubElement(exit_road, 'objects')
    ET.SubElement(exit_road, 'signals')
    return ET.tostring(root, encoding='unicode')

def check():
    root = ET.fromstring(open_drive())
    roads = root.findall('road')
    if len(roads) != 2 or [r.attrib['id'] for r in roads] != ['1', '2']:
        raise ValueError('roundabout and exit roads changed')
    if roads[0].find('planView/geometry/arc') is None or roads[1].find('planView/geometry/line') is None:
        raise ValueError('roundabout curvature or exit tangent missing')
    if any([l.attrib['id'] for l in r.findall('lanes/laneSection/right/lane')] != ['-1', '-2'] for r in roads):
        raise ValueError('two-lane allocation changed')
    return {'passed': True, 'roundabout_radius_m': RADIUS_M, 'arc_length_m': ARC_M, 'exit_length_m': EXIT_M, 'lane_ids': [-1, -2], 'native_connectivity_verified': False}

if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
