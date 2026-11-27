"""Validate an operator's original map/device survey before Native capture."""

import json
from pathlib import Path

from controller import SUFFIXES

ASSIGNMENT = 'training__C111603__NRS-484B-307-4a__motor_vehicle_driver'
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def load(path, case_id):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Original governed-arrow intersection survey required')
    survey = json.loads(path.read_text())
    required = (
        'case_id', 'source_kind', 'map_name', 'ego_spawn_xyz_yaw',
        'pedestrian_spawn_xyz_yaw', 'other_traffic_spawn_xyz_yaw',
        'indicated_turn_waypoints_xy', 'contrary_turn_waypoints_xy',
        'arrow_opendrive_id', 'arrow_direction', 'arrow_facing_source',
        'arrow_only_pixels_source', 'intersection_bounds_m',
        'adjacent_crosswalk_bounds_m', 'pedestrian_permission_source',
        'other_traffic_permission_source', 'camera_poses',
    )
    if (case_id not in [ASSIGNMENT + '__' + suffix for suffix in SUFFIXES]
            or survey.get('case_id') != case_id
            or survey.get('source_kind') != 'original_native_context_survey'
            or any(not survey.get(key) for key in required)):
        raise ValueError('Original governed-arrow survey identity or source incomplete')
    if survey['arrow_direction'] not in ('left', 'right'):
        raise ValueError('Original arrow direction missing')
    if set(survey['camera_poses']) != {'overview', 'reference_corner'}:
        raise ValueError('Two original fixed-camera poses required')
    for key in ('intersection_bounds_m', 'adjacent_crosswalk_bounds_m'):
        bounds = survey[key]
        if (len(bounds) != 4 or not all(isinstance(x, (int, float)) for x in bounds)
                or bounds[0] >= bounds[1] or bounds[2] >= bounds[3]):
            raise ValueError('Original spatial bounds invalid: ' + key)
    for key in ('indicated_turn_waypoints_xy', 'contrary_turn_waypoints_xy'):
        points = survey[key]
        if len(points) < 3 or any(len(point) != 2 for point in points):
            raise ValueError('Original turn route incomplete: ' + key)
    if survey['indicated_turn_waypoints_xy'] == survey['contrary_turn_waypoints_xy']:
        raise ValueError('Direction comparison has identical source routes')
    return survey
