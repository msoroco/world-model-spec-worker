"""Authored non-through intersection and explicit entrance-control inventory.

This is an executable construction request. Original CARLA map semantics and
control state must be read back before a Native delivery can be accepted.
"""
from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET

ENTRANCES = ('west_subject', 'east_opposing', 'south_crossing', 'north_counterpart')
CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(value, message):
    if not value:
        raise ValueError(message)


def open_drive(subject_sign='stop', reference='stop_line', signal=False, counterpart_control='none'):
    require(subject_sign in {'stop', 'yield'}, 'Unsupported subject sign')
    require(reference in {'stop_line', 'crosswalk', 'nearest_viewpoint'}, 'Unsupported reference')
    require(counterpart_control in {'none', 'stop', 'yield'}, 'Unsupported counterpart control')
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4', name='C111325-nonthru-crossroad',
                  version='1', north='100', south='-100', east='100', west='-100',
                  vendor='full-train-worker')
    for road_id, name, x, y, heading in ((111325, 'subject_local_road', -80, 0, 0),
                                         (111326, 'crossing_local_road', 0, -80, math.pi / 2)):
        road = ET.SubElement(root, 'road', id=str(road_id), name=name, length='160', junction='-1',
                             rule='RHT')
        ET.SubElement(road, 'link')
        geom = ET.SubElement(ET.SubElement(road, 'planView'), 'geometry', s='0', x=str(x),
                             y=str(y), hdg=str(heading), length='160')
        ET.SubElement(geom, 'line')
        ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation', s='0', a='0', b='0', c='0', d='0')
        lanes = ET.SubElement(road, 'lanes')
        ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
        section = ET.SubElement(lanes, 'laneSection', s='0')
        for side, ident in (('left', 1), ('center', 0), ('right', -1)):
            lane = ET.SubElement(ET.SubElement(section, side), 'lane', id=str(ident),
                                 type='none' if ident == 0 else 'driving', level='false')
            if ident:
                ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        objects = ET.SubElement(road, 'objects')
        signals = ET.SubElement(road, 'signals')
        if road_id == 111325:
            if reference == 'stop_line':
                ET.SubElement(objects, 'object', id='line-111325', name='marked-stop-line',
                              type='roadMark', s='74', t='0', zOffset='0', hdg='0',
                              length='0.4', width='7', height='0')
            elif reference == 'crosswalk':
                ET.SubElement(objects, 'object', id='crosswalk-111325', name='near-side-crosswalk',
                              type='crosswalk', s='75', t='0', zOffset='0', hdg='0',
                              length='1', width='7', height='0')
            ET.SubElement(signals, 'signal', id=f'{subject_sign}-111325', s='74', t='-3.7',
                          name=subject_sign.upper(), dynamic='no', orientation='+', zOffset='0',
                          country='US', type='205' if subject_sign == 'yield' else '206',
                          subtype='0', value='0', unit='', height='0.8', width='0.8')
            if signal:
                ET.SubElement(signals, 'signal', id='traffic-signal-111325', s='75', t='-3.7',
                              name='TRAFFIC_SIGNAL', dynamic='yes', orientation='+', zOffset='0',
                              country='US', type='1000001', subtype='0', value='0', unit='',
                              height='3', width='0.5')
        elif counterpart_control != 'none':
            ET.SubElement(signals, 'signal', id=f'{counterpart_control}-111326', s='74', t='-3.7',
                          name=counterpart_control.upper(), dynamic='no', orientation='+', zOffset='0',
                          country='US', type='205' if counterpart_control == 'yield' else '206',
                          subtype='0', value='0', unit='', height='0.8', width='0.8')
    return ET.tostring(root, encoding='unicode')


def request(case, sign='stop', reference='stop_line', counterpart_control='none',
            exception=None, counterpart_start_y=-50, action='stop_then_yield'):
    require(exception in {None, 'police', 'signal'}, 'Unknown exception')
    require(counterpart_control in {'none', 'stop', 'yield'}, 'Unknown counterpart control')
    inventory = {'west_subject': sign, 'east_opposing': 'none',
                 'south_crossing': 'none', 'north_counterpart': counterpart_control}
    return {
        'format': 'c111325-257-2-nonthrough-native-request-v1', 'case': case,
        'road_opendrive': open_drive(sign, reference, exception == 'signal', counterpart_control),
        'road_kind_requested': 'non_through_highway',
        'road_kind_native_verified': False,
        'entrance_control_inventory_requested': inventory,
        'entrance_control_inventory_native_verified': False,
        'subject_control': sign, 'counterpart_control': counterpart_control,
        'subject_governing_sign_id': f'{sign}-111325',
        'stop_reference': reference,
        'reference_source_required': 'original map markings and front bumper samples',
        'counterpart_obligation_source_required': 'original all-entrance sign inventory and actor lane',
        'control_exception': exception,
        'exception_source_required': ('original officer identity and direction' if exception == 'police' else
                                      'original governing signal state' if exception == 'signal' else None),
        'ego': {'blueprint': 'vehicle.tesla.model3', 'start_xyz': [-45, -1.75, 0.5],
                'heading_deg': 0, 'body_length_m': 4.5},
        'counterpart': {'blueprint': 'vehicle.tesla.model3', 'start_xyz': [1.75, counterpart_start_y, 0.5],
                        'heading_deg': 90, 'body_length_m': 4.5, 'requested_speed_mps': 5.0},
        'controller': {'requested_action': action, 'release_frame': 250,
                       'reference_front_x_m': -7 if reference == 'stop_line' else
                                              -6 if reference == 'crosswalk' else -4.1},
        'cameras': [
            {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 80, 'xyz': [-14, -14, 20], 'pitch': -45, 'yaw': 35, 'pose_strategy': 'fixed surveyed whole intersection'},
            {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 80, 'xyz': [-20, -10, 9], 'pitch': -20, 'yaw': 25, 'pose_strategy': 'fixed governed approach'},
            {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fov_deg': 80, 'xyz': [-8, -11, 6], 'pitch': -20, 'yaw': 30, 'pose_strategy': 'fixed stopping reference'},
            {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 80, 'xyz': [1, 0, 2], 'pitch': -8, 'yaw': 0, 'attach_to_ego': True, 'pose_strategy': 'attached driver reference'},
        ],
        'rate_hz': 20, 'planned_frames': 600, 'duration_s': 30,
        'physical_success_claimed': False, 'legal_result': None,
    }


def validate(req):
    root = ET.fromstring(req['road_opendrive'])
    roads = {road.attrib.get('id'): road for road in root.findall('road')}
    require(root.tag == 'OpenDRIVE' and set(roads) == {'111325', '111326'}, 'Two local roads missing')
    require(all('local_road' in road.attrib.get('name', '') for road in roads.values()),
            'Non-through road request missing')
    require(all(road.find('planView/geometry/line') is not None for road in roads.values()),
            'Crossing geometry missing')
    require(req['road_kind_requested'] == 'non_through_highway' and not req['road_kind_native_verified'],
            'Road-kind source claim invalid')
    inventory = req['entrance_control_inventory_requested']
    require(set(inventory) == set(ENTRANCES), 'Whole-intersection entrance inventory missing')
    require(inventory['west_subject'] == req['subject_control'] and
            inventory['north_counterpart'] == req['counterpart_control'], 'Entrance obligation mismatch')
    require(not req['entrance_control_inventory_native_verified'], 'Unsourced entrance inventory claim')
    subject_signals = roads['111325'].findall('signals/signal')
    counterpart_signals = roads['111326'].findall('signals/signal')
    if req['counterpart_control'] == 'none':
        require(not counterpart_signals, 'Counterpart approach unexpectedly signed')
    else:
        require(len(counterpart_signals) == 1 and
                counterpart_signals[0].attrib.get('id') == f"{req['counterpart_control']}-111326" and
                counterpart_signals[0].attrib.get('name') == req['counterpart_control'].upper(),
                'Counterpart approach sign missing')
    require(subject_signals and subject_signals[0].attrib.get('id') == req['subject_governing_sign_id'] and
            subject_signals[0].attrib.get('name') == req['subject_control'].upper(), 'Governing sign missing')
    reference = req['stop_reference']
    objects = roads['111325'].findall('objects/object')
    require((reference == 'nearest_viewpoint' and not objects) or
            (reference == 'stop_line' and len(objects) == 1 and objects[0].attrib.get('type') == 'roadMark') or
            (reference == 'crosswalk' and len(objects) == 1 and objects[0].attrib.get('type') == 'crosswalk'),
            'Stopping reference hierarchy mismatch')
    require(set(c['name'] for c in req['cameras']) == set(CAMERAS) and
            all((c['width'], c['height']) == CAMERAS[c['name']] and c.get('pose_strategy') and
            isinstance(c.get('xyz'), list) and len(c['xyz']) == 3 and c.get('fov_deg')
                for c in req['cameras']), 'Exact four-camera plan missing')
    require(req['rate_hz'] == 20 and req['planned_frames'] == 600 and req['duration_s'] == 30,
            'Exact thirty-second plan missing')
    exception = req['control_exception']
    require(exception in {None, 'police', 'signal'}, 'Unknown exception')
    require(bool(req['exception_source_required']) == (exception is not None), 'Exception source missing')
    require(len(subject_signals) == (2 if exception == 'signal' else 1), 'Signal construction mismatch')
    require(not req['physical_success_claimed'] and req['legal_result'] is None,
            'Unsourced physical or legal claim')
    return {'case': req['case'], 'road_count': 2, 'entrances_inventoried': 4,
            'camera_count': 4, 'planned_frames': 600,
            'opendrive_sha256': hashlib.sha256(req['road_opendrive'].encode()).hexdigest(),
            'original_road_kind_verified': False, 'original_controls_verified': False}
