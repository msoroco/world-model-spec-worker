"""Near-side crosswalk Native construction proposal; CARLA execution is local only."""
from pathlib import Path
import argparse
import json
import math
import xml.etree.ElementTree as ET

ASSIGNMENT = 'training__C111325__NRS-484A-450-2__motor_vehicle_driver'
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
    target = 0.0 if case.endswith('probe_1') and 120 <= index < 180 else 4.0
    return {'target_speed_mps': target,
            'requested_pre_crosswalk_stop': case.endswith('probe_1') and 120 <= index < 180}


def capture_row(index, frame, elapsed_s, actor, waypoint):
    """Extract original post-tick pose, velocity and full vehicle body."""
    if type(index) is not int or not 0 <= index < FRAMES or type(frame) is not int:
        raise ValueError('Original Native frame identity absent')
    if not isinstance(elapsed_s, (int, float)) or not math.isfinite(elapsed_s):
        raise ValueError('Original Native time absent')
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) != 8 or waypoint is None:
        raise ValueError('Original body or lane projection absent')
    return {'video_frame': index, 'native_frame': frame, 'time_s': elapsed_s,
            'source_kind': 'native_observation', 'actor_id': actor.id,
            'blueprint_id': actor.type_id, 'road_id': waypoint.road_id,
            'lane_id': waypoint.lane_id,
            'center_m': [transform.location.x, transform.location.y, transform.location.z],
            'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            'body_vertices_m': [[v.x, v.y, v.z] for v in vertices]}


def check(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484A-450-2', 'C111325', 'motor_vehicle_driver'):
        raise ValueError('Exact frozen identity differs')
    if config.get('case_id') not in (ASSIGNMENT + '__probe_1', ASSIGNMENT + '__probe_2'):
        raise ValueError('Exact case identity differs')
    if config.get('rate_hz') != RATE_HZ or config.get('duration_s') != 30:
        raise ValueError('Full 600-frame duration differs')
    declared = [(camera['name'], camera['width'], camera['height'])
                for camera in config.get('cameras', [])]
    if declared != list(CAMERAS):
        raise ValueError('Current four-camera profile differs')
    root = ET.parse(HERE / 'authored-road.xodr').getroot()
    roads = {int(road.get('id')) for road in root.findall('road')}
    approach = next(road for road in root.findall('road') if road.get('id') == '1')
    signs = approach.findall('signals/signal')
    crossings = approach.findall('objects/object')
    if roads != {1, 2, 3, 4, 13, 14} or not any(s.get('name') == 'STOP' for s in signs) \
            or not any(o.get('type') == 'crosswalk' for o in crossings):
        raise ValueError('Authored sign/crosswalk approach geometry differs')
    expected = 0 if config['case_id'].endswith('probe_1') else 4
    if request(140, config['case_id'])['target_speed_mps'] != expected:
        raise ValueError('Controlled stop request differs')
    return {'passed': True, 'case_id': config['case_id'], 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'cameras': [c[0] for c in CAMERAS],
            'road_ids': sorted(roads), 'native_imported': False,
            'native_capture_implemented': False, 'physical_observation_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        raise SystemExit('Native capture/controller loop remains unfinished')
    print(json.dumps(check(json.loads((HERE / 'config.json').read_text())), sort_keys=True))
