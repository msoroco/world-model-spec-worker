"""C111334 pedestrian crossing construction request; CPU checks never import CARLA.

The authored OpenDRIVE signal is a physical request. Native state readback alone
cannot establish a *turn arrow alone*, its facing, or pedestrian permission.
Those facts require original device/camera evidence in saved processing.
"""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C111334__NRS-484B-307-4b__pedestrian'
CASES = ('probe_1', 'probe_2', 'permission_before_entry')
VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('signal_close', 1280, 720), ('pedestrian_reference', 1280, 720))
ARROW_ID = 'C111334-facing-green-turn-arrow'
PERMISSION_ID = 'C111334-other-permitting-device'
CROSSWALK_ID = 'C111334-highway-crossing'


def proposal(suffix):
    if suffix not in CASES:
        raise ValueError('Unknown exact pedestrian entry case')
    return {
        'format': 'c111334-native-entry-proposal-v1',
        'case_id': ASSIGNMENT + '__' + suffix,
        'cell': {'layout': 'intersection', 'maneuver': 'travel', 'control': 'turn_arrow'},
        'actor': 'pedestrian', 'rate_hz': 20, 'duration_s': 30, 'frames': 600,
        'map': 'road.xodr', 'crosswalk_id': CROSSWALK_ID,
        'arrow_head_id': ARROW_ID, 'other_device_id': PERMISSION_ID,
        'requested_arrow_display': 'green_turn_arrow_alone',
        'requested_permission_start_frame': 100 if suffix == 'permission_before_entry' else None,
        'requested_walker_start_xy_m': [0.0, 4.0],
        'requested_walker_direction_xy': [0.0, -1.0],
        'requested_walker_speed_mps': 1.0,
        'requested_walker_move_start_frame': None if suffix == 'probe_1' else 120,
        'highway_bounds_y_m': [-3.0, 3.0],
        'cameras': [{'name': name, 'width': width, 'height': height}
                    for name, width, height in VIEWS],
        'required_original_sources': [
            'Native pedestrian identity, footprint, pose and frame clock',
            'Native map highway boundary and route geometry',
            'Original green-turn-arrow-alone head pixels and facing audit',
            'Original other-device pixels, governing authority and permission timing',
            'Four decoded source-camera streams and frame identity hashes'],
        'status': 'construction_request_physical_unverified',
    }


def check_map(path=HERE / 'road.xodr'):
    root = ET.parse(path).getroot()
    roads = root.findall('road')
    if len(roads) != 2 or len(root.findall('junction')) != 1:
        raise ValueError('Two-road intersection and junction required')
    objects = [obj for road in roads for obj in road.findall('objects/object')]
    crosswalks = [obj for obj in objects if obj.get('name') == CROSSWALK_ID
                  and obj.get('type') == 'crosswalk']
    if len(crosswalks) != 1:
        raise ValueError('Named highway crossing absent')
    signals = [sig for road in roads for sig in road.findall('signals/signal')]
    if {sig.get('name') for sig in signals} != {ARROW_ID, PERMISSION_ID}:
        raise ValueError('Two distinct named signal objects required')
    if {sig.get('id') for sig in signals} != {'201', '202'}:
        raise ValueError('Signal source identities differ')
    return {'authored_map_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'roads': len(roads), 'crosswalk': CROSSWALK_ID,
            'signals': [ARROW_ID, PERMISSION_ID], 'native_loaded': False,
            'turn_arrow_pixels_verified': False, 'other_device_authority_verified': False}


def check_comparisons():
    geometry = check_map()
    plans = {suffix: proposal(suffix) for suffix in CASES}
    fixed = ('cell', 'actor', 'rate_hz', 'duration_s', 'frames', 'map',
             'crosswalk_id', 'arrow_head_id', 'other_device_id',
             'requested_arrow_display', 'requested_walker_start_xy_m',
             'requested_walker_direction_xy', 'requested_walker_speed_mps',
             'highway_bounds_y_m', 'cameras')
    if any(plan[key] != plans['probe_2'][key]
           for plan in plans.values() for key in fixed):
        raise ValueError('Comparison fixed conditions differ')
    if plans['probe_1']['requested_walker_move_start_frame'] is not None or \
            plans['probe_2']['requested_walker_move_start_frame'] != 120 or \
            plans['permission_before_entry']['requested_walker_move_start_frame'] != 120:
        raise ValueError('Wait/entry trajectory comparison differs')
    if plans['probe_2']['requested_permission_start_frame'] is not None or \
            plans['permission_before_entry']['requested_permission_start_frame'] != 100:
        raise ValueError('Other-device permission comparison differs')
    return {'geometry': geometry, 'case_ids': [plans[s]['case_id'] for s in CASES],
            'comparisons': {'wait_vs_entry': ['probe_1', 'probe_2'],
                            'permission_at_same_entry': ['probe_2', 'permission_before_entry']},
            'native_executed': False, 'legal_outcome_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check_comparisons(), sort_keys=True))
