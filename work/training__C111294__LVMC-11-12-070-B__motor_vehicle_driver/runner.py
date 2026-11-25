"""Thirty-second two-actor Native capture proposal; CPU preflight is offline."""
from pathlib import Path
import argparse
import json
import math
import xml.etree.ElementTree as ET

ASSIGNMENT = 'training__C111294__LVMC-11-12-070-B__motor_vehicle_driver'
FRAMES = 600
RATE_HZ = 20
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
HERE = Path(__file__).resolve().parent


def request(index, case):
    if type(index) is not int or not 0 <= index < FRAMES:
        raise ValueError('Frame outside exact 30-second request')
    if case not in (ASSIGNMENT + '__probe_1', ASSIGNMENT + '__probe_2'):
        raise ValueError('Unknown proposed case')
    # Engineering timing requests only. The actual actor histories must be read
    # back from CARLA, never inferred from this request schedule.
    ego_speed = (8.0 if index < 142 or index >= 335 else 0.0) if case.endswith('probe_1') else 8.0
    entrant_speed = 0.0 if index < 110 else (2.0 if index < 320 else 5.0)
    return {'through_target_speed_mps': ego_speed,
            'entrant_target_speed_mps': entrant_speed,
            'requested_yield_hold': case.endswith('probe_1') and 142 <= index < 335}


def capture_row(index, frame, elapsed_s, through, entrant, through_waypoint, entrant_waypoint):
    """Extract observed post-tick CARLA body/pose/velocity for later capture code."""
    if type(index) is not int or not 0 <= index < FRAMES or type(frame) is not int:
        raise ValueError('Native frame identity absent')
    if not isinstance(elapsed_s, (int, float)) or not math.isfinite(elapsed_s):
        raise ValueError('Native elapsed time absent')
    if through_waypoint is None or entrant_waypoint is None:
        raise ValueError('Original road/lane projection absent')
    actors = {}
    for name, actor, waypoint in (('through', through, through_waypoint),
                                  ('entrant', entrant, entrant_waypoint)):
        transform = actor.get_transform()
        velocity = actor.get_velocity()
        vertices = actor.bounding_box.get_world_vertices(transform)
        if len(vertices) != 8:
            raise ValueError('Full Native vehicle body absent')
        actors[name] = {'actor_id': actor.id, 'blueprint_id': actor.type_id,
                        'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                        'x_m': transform.location.x, 'y_m': -transform.location.y,
                        'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
                        'velocity_mps': [velocity.x, -velocity.y, velocity.z],
                        'body_vertices_m': [[v.x, -v.y, v.z] for v in vertices]}
    return {'video_frame': index, 'native_frame': frame, 'time_s': elapsed_s,
            'through': actors['through'], 'entrant': actors['entrant'],
            'source_kind': 'native_observation'}


def check(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-12-070-B', 'C111294', 'motor_vehicle_driver'):
        raise ValueError('Exact frozen case identity differs')
    if config['case_id'] not in (ASSIGNMENT + '__probe_1', ASSIGNMENT + '__probe_2'):
        raise ValueError('Exact frozen case identity differs')
    if config.get('rate_hz') != RATE_HZ or config.get('duration_s') != 30:
        raise ValueError('Full 600-frame duration differs')
    declared = [(camera['name'], camera['width'], camera['height'])
                for camera in config.get('cameras', [])]
    if declared != list(CAMERAS):
        raise ValueError('Current four-camera profile differs')
    road_path = HERE / 'authored-road.xodr'
    if not road_path.is_file():
        road_path = HERE / 'road.xodr'
    tree = ET.parse(road_path)
    roads = {int(item.attrib['id']) for item in tree.findall('road')}
    links = {(item.attrib['incomingRoad'], item.attrib['connectingRoad'])
             for item in tree.findall('junction/connection')}
    if roads != {1, 2, 3, 4, 13, 14} or not {('1', '13'), ('3', '14')} <= links:
        raise ValueError('Authored through/entrant geometry differs')
    if request(0, config['case_id'])['through_target_speed_mps'] <= 0:
        raise ValueError('Through approach request absent')
    expected_speed = 0 if config['case_id'].endswith('probe_1') else 8
    if request(200, config['case_id'])['through_target_speed_mps'] != expected_speed:
        raise ValueError('Through response request differs')
    return {'passed': True, 'case_id': config['case_id'], 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'cameras': [item[0] for item in CAMERAS],
            'road_ids': sorted(roads), 'native_imported': False,
            'native_capture_implemented': True, 'physical_observation_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        raise SystemExit('Run live_capture.py with an exact offline bundle and fresh output')
    print(json.dumps(check(json.loads((HERE / 'config.json').read_text())), sort_keys=True))
