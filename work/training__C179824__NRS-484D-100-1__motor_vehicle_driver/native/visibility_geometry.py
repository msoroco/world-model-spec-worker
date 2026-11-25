"""Seven-hundred-metre paved-road geometry for the 1,000-foot trigger probe.

The configured reference is an engineering target, not a claim of discernibility.
An original image/source audit must decide whether each object is clearly visible.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET


ROAD_START_M = -350.0
ROAD_LENGTH_M = 700.0
STATUTORY_DISTANCE_M = 304.8
EGO_REFERENCE_X_M = -200.0
TARGET_REFERENCE_X_M = EGO_REFERENCE_X_M + STATUTORY_DISTANCE_M


def open_drive():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C179824-1000ft-visibility', version='1',
                  date='2026-11-25', north='12', south='-12',
                  east='350', west='-350', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id='1', name='paved-visibility-road',
                         length=str(ROAD_LENGTH_M), junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x=str(ROAD_START_M), y='0', hdg='0',
                             length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(section, 'left')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0',
                  type='none', level='false')
    right = ET.SubElement(section, 'right')
    for lane_id, kind, width in ((-1, 'driving', 3.5), (-2, 'shoulder', 2.5)):
        lane = ET.SubElement(right, 'lane', id=str(lane_id), type=kind,
                             level='false')
        ET.SubElement(lane, 'width', sOffset='0', a=str(width),
                      b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid',
                      color='white', width='.1')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode')


def check(distance_m=STATUTORY_DISTANCE_M):
    root = ET.fromstring(open_drive())
    road = root.find('road')
    if road is None:
        raise ValueError('visibility roadway missing')
    geometry = road.find('planView/geometry')
    if geometry is None:
        raise ValueError('visibility roadway geometry missing')
    target = EGO_REFERENCE_X_M + distance_m
    if abs(distance_m - STATUTORY_DISTANCE_M) > 0.304800001:
        raise ValueError('boundary reference must be within one foot of 1,000 feet')
    if not ROAD_START_M < EGO_REFERENCE_X_M < target < ROAD_START_M + ROAD_LENGTH_M:
        raise ValueError('reference targets outside road')
    if float(geometry.attrib['length']) != ROAD_LENGTH_M:
        raise ValueError('visibility road length changed')
    if [int(lane.attrib['id']) for lane in road.findall('lanes/laneSection/right/lane')] != [-1, -2]:
        raise ValueError('visibility lane layout changed')
    return {'passed': True, 'road_length_m': ROAD_LENGTH_M,
            'ego_reference_x_m': EGO_REFERENCE_X_M,
            'target_reference_x_m': target,
            'reference_distance_m': distance_m,
            'person_and_vehicle_pixels_verified': False}


if __name__ == '__main__':
    import json
    print(json.dumps(check(), sort_keys=True))
