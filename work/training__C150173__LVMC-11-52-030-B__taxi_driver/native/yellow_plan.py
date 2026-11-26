"""Exact source-shaped taxi yellow-zone request, without a legal verdict."""
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

PREFIX = 'training__C150173__LVMC-11-52-030-B__taxi_driver__'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
PURPOSES = {'probe_a': (10, 'waiting_for_passengers'),
            'probe_b': (18, 'waiting_for_passengers'),
            'probe_c': (10, 'loading_passengers'),
            'probe_d': (10, 'unloading_passengers')}


def check(config, road_text):
    if (config.get('case_id') not in tuple(PREFIX + key for key in PURPOSES) or
            config.get('cell_id') != 'C150173' or
            config.get('law_id') != 'LVMC-11-52-030-B' or
            config.get('actor') != 'taxi_driver' or
            config.get('duration_s') != 30 or config.get('rate_hz') != 20 or
            config.get('frames') != 600 or config.get('legal_verdict') is not None):
        raise ValueError('Frozen taxi yellow-zone identity or duration differs')
    if tuple(c.get('name') for c in config.get('cameras', [])) != VIEWS:
        raise ValueError('Four original source cameras required')
    if any(c.get('fps') != 20 or not all(c.get(k) for k in
           ('width', 'height', 'fov_deg', 'location_xyz_m', 'rotation_pyr_deg'))
           for c in config['cameras']):
        raise ValueError('Camera geometry or rate missing')
    if config.get('taxi_blueprint_filter') != 'vehicle.*':
        raise ValueError('Unreviewed taxi blueprint filter')
    stop_x = config.get('taxi_stop_x_m')
    if type(stop_x) not in (int, float) or not math.isfinite(stop_x) or not 4.5 <= stop_x <= 5.5:
        raise ValueError('Yellow curb stop coordinate missing')
    suffix = config['case_id'][len(PREFIX):]
    hour, purpose = PURPOSES[suffix]
    if config.get('requested_purpose') != purpose:
        raise ValueError('Exact passenger purpose request differs')
    if config.get('sign_source_status') != 'authored_proposal_unverified':
        raise ValueError('Sign authority must remain unverified')
    if config.get('ordinary_rules_outside_hours') != 'unresolved':
        raise ValueError('Outside-hours ordinary rules may not be decided by this probe')
    start = datetime.fromisoformat(config['civil_start_local'])
    if start.tzinfo is not None or start.minute or start.second or start.microsecond:
        raise ValueError('Exact local civil hour required')
    if start.hour != hour:
        raise ValueError('Case civil-hour contrast differs')
    road = ET.fromstring(road_text).find('road')
    if road is None or road.find('./planView/geometry/line') is None:
        raise ValueError('One-way road geometry missing')
    lanes = {(node.get('id'), node.get('type')): node for node in
             road.findall('./lanes/laneSection/right/lane')}
    if {('-1', 'driving'), ('-2', 'parking'), ('-3', 'sidewalk')} - lanes.keys():
        raise ValueError('Driving, parking or sidewalk lane missing')
    marks = lanes[('-2', 'parking')].findall('roadMark')
    if not any(mark.get('color') == 'yellow' for mark in marks):
        raise ValueError('Yellow parking curb marking missing')
    if not any(node.get('name') == 'TAXI PASSENGERS 09:00-17:00 PROPOSAL'
               and 80 <= float(node.get('s', '-1')) <= 90
               for node in road.findall('signals/signal')):
        raise ValueError('Posted-hours sign proposal missing')
    if not any(node.get('id') == '701' and float(node.get('s', '-1')) <= 90 <=
               float(node.get('s', '-1')) + float(node.get('length', '0'))
               for node in road.findall('objects/object')):
        raise ValueError('Yellow zone geometry missing')
    return {'frames': 600, 'rate_hz': 20, 'source_cameras': list(VIEWS),
            'civil_start_local': config['civil_start_local'],
            'sign_authority_verified': False, 'passenger_purpose_verified': False,
            'ordinary_rules_resolved': False, 'carla_contacted': False}


def measure_requested(rows, config):
    if len(rows) != 600:
        raise ValueError('Full 600-frame request required')
    start = datetime.fromisoformat(config['civil_start_local'])
    active = 0
    for i, row in enumerate(rows):
        if (row.get('video_frame') != i or
                not math.isclose(row.get('time_s', -1), (i + 1) / 20, abs_tol=1e-8) or
                row.get('source_kind') != 'authored_native_request'):
            raise ValueError('Requested Native frame/time/source join differs')
        if row.get('requested_taxi_role') != 'taxi_unverified' or row.get('requested_speed_mps') != 0:
            raise ValueError('Taxi parking request missing')
        if row.get('requested_purpose') != config['requested_purpose']:
            raise ValueError('Passenger purpose request missing')
        civil = datetime.fromisoformat(row['civil_time_local'])
        if civil != start + timedelta(seconds=(i + 1) / 20):
            raise ValueError('Civil time join differs')
        if row.get('requested_stop_xy_m') != [config['taxi_stop_x_m'], 10.0]:
            raise ValueError('Yellow curb stop request differs')
        active += '09:00' <= civil.strftime('%H:%M') < '17:00'
    return {'requested_frames': 600, 'sign_active_request_frames': active,
            'sign_authority_verified': False, 'passenger_purpose_verified': False,
            'legal_verdict': None}


def read_requested(path, config):
    return measure_requested([json.loads(line) for line in Path(path).read_text().splitlines()], config)
