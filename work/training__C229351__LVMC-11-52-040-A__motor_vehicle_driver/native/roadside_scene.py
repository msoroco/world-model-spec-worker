"""Offline checks for exact roadway-edge rest requests, without legal cutoffs."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

from cameras import check as check_cameras
from selected_plan import AID, CASES, CELL


def check(config, road_text):
    case = config.get('case_id')
    if case not in CASES or config.get('selected_case_id') != case:
        raise ValueError('Exact selected case differs')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-52-040-A', 'C229351', 'motor_vehicle_driver'):
        raise ValueError('Frozen assignment identity differs')
    if (config.get('layout'), config.get('maneuver'), config.get('control')) != (
            CELL['layout'], CELL['maneuver'], CELL['control']):
        raise ValueError('Frozen roadway cell differs')
    if (config.get('rate_hz'), config.get('duration_s'), config.get('duration_frames')) != (20, 30, 600):
        raise ValueError('Full synchronized source window differs')
    if set(config.get('supported_case_ids', [])) != set(CASES):
        raise ValueError('Six-case coverage differs')
    if (config.get('activity_requested'), config.get('rest_pose_requested'),
            config.get('requested_yaw_offset_deg')) != (
            CASES[case]['activity'], CASES[case]['pose'], CASES[case]['requested_yaw_offset_deg']):
        raise ValueError('Requested activity or orientation differs')
    if config.get('controller_mode') not in ('service_brake', 'service_and_hand_brake'):
        raise ValueError('Undeclared at-rest controller mode')
    if config.get('required_atoms') != ['kin.heading', 'kin.speed']:
        raise ValueError('Supported native telemetry differs')
    check_cameras(config.get('cameras', []))
    root = ET.fromstring(road_text)
    lane = root.find("./road/lanes/laneSection/right/lane[@id='-1']")
    sidewalk = root.find("./road/lanes/laneSection/right/lane[@id='-2']")
    width = None if lane is None else lane.find('width')
    geometry = root.find('./road/planView/geometry')
    if lane is None or lane.get('type') != 'driving' or sidewalk is None or \
            sidewalk.get('type') != 'sidewalk' or width is None or geometry is None:
        raise ValueError('Identifiable driving roadway and separate outside edge required')
    road_width = float(width.get('a'))
    heading_deg = math.degrees(float(geometry.get('hdg')))
    center_x = config.get('requested_rest_center_x_m')
    if not isinstance(center_x, (int, float)) or not math.isfinite(center_x):
        raise ValueError('Finite resting center required')
    yaw = heading_deg + config['requested_yaw_offset_deg']
    half_length, half_width = 2.5, 1.0
    lateral_extent = abs(half_length * math.cos(math.radians(yaw))) + \
        abs(half_width * math.sin(math.radians(yaw)))
    if not (center_x - lateral_extent > 0 and center_x + lateral_extent < road_width):
        raise ValueError('Authored vehicle footprint crosses roadway edge')
    return {'case_id': case, 'frames': 600, 'road_width_m': road_width,
            'authored_lawful_yaw_deg': heading_deg,
            'requested_yaw_deg': yaw, 'requested_center_x_m': center_x,
            'authored_footprint_inside_driving_roadway': True,
            'original_native_observed': False, 'actual_activity_review_required': True,
            'chapter_exception_review_required': True, 'legal_result': None}
