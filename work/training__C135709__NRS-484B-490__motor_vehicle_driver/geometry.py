"""Requested narrow-highway geometry and prohibitory device for C135709.

OpenDRIVE geometry is an engineering request. Narrow-highway designation,
official device authority, erection, and governed extent require original
independent source review after capture.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

ROAD_ID = 1
DEVICE_ID = '490'
DEVICE_NAME = 'NO PARKING NARROW HIGHWAY'
GOVERNED_X_M = (-20.0, 20.0)
PARK_X_M = {'probe_01': 35.0, 'probe_02': 0.0}
PARK_Y_M = -2.0


def open_drive() -> str:
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C135709-narrow-highway',
                  version='1', date='2026-11-26', north='8', south='-8', east='70',
                  west='-70', vendor='full-train-worker')
    road = ET.SubElement(root, 'road', id=str(ROAD_ID), name='narrow-highway',
                         length='140', junction='-1')
    ET.SubElement(road, 'link')
    geometry = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                             s='0', x='-70', y='0', hdg='0', length='140')
    ET.SubElement(geometry, 'line')
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    ET.SubElement(ET.SubElement(section, 'center'), 'lane', id='0', type='none', level='false')
    for side, lane_id in (('left', 1), ('right', -1)):
        parent = ET.SubElement(section, side)
        lane = ET.SubElement(parent, 'lane', id=str(lane_id), type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='2.8', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='solid', color='white', width='.1')
    ET.SubElement(road, 'objects')
    signals = ET.SubElement(road, 'signals')
    ET.SubElement(signals, 'signal', id=DEVICE_ID, s='45', t='-3.1',
                  name=DEVICE_NAME, dynamic='no', orientation='-', zOffset='2',
                  country='USA', type='parking_restriction', subtype='no_parking',
                  value='0', unit='none', hOffset='0', pitch='0', roll='0')
    return ET.tostring(root, encoding='unicode')


def check() -> dict:
    root = ET.fromstring(open_drive())
    road = root.find('road')
    if road is None or road.attrib.get('id') != str(ROAD_ID):
        raise ValueError('narrow-highway road identity changed')
    lane_rows = [(int(x.attrib['id']), x.attrib['type'], float(x.find('width').attrib['a']))
                 for x in root.findall('road/lanes/laneSection/left/lane') +
                          root.findall('road/lanes/laneSection/right/lane')]
    if lane_rows != [(1, 'driving', 2.8), (-1, 'driving', 2.8)]:
        raise ValueError('two-way narrow lane geometry changed')
    signs = root.findall('road/signals/signal')
    if len(signs) != 1 or signs[0].attrib.get('id') != DEVICE_ID or \
            signs[0].attrib.get('name') != DEVICE_NAME or \
            signs[0].attrib.get('subtype') != 'no_parking':
        raise ValueError('prohibitory device request changed')
    if PARK_X_M['probe_01'] - 2.5 <= GOVERNED_X_M[1] or \
            not (GOVERNED_X_M[0] + 2.5 < PARK_X_M['probe_02'] < GOVERNED_X_M[1] - 2.5):
        raise ValueError('parking contrast does not separate extents')
    return {'road_id': ROAD_ID, 'lane_width_m': 2.8,
            'requested_device_id': DEVICE_ID, 'governed_x_m': list(GOVERNED_X_M),
            'parking_x_m': PARK_X_M, 'physical_verified': False,
            'official_authority_verified': False, 'legal_narrowness_verified': False}
