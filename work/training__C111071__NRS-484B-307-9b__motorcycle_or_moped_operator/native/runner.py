"""C111071 exact-case preflight and original Native capture entrypoint."""
from pathlib import Path
import argparse
import json
import math

from cycle_controller import EGO_FACE, FRAMES, RATE_HZ, Sample, commanded_brake

ASSIGNMENT = 'training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator'
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def check(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-307-9b', 'C111071', 'motorcycle_or_moped_operator'):
        raise ValueError('Exact frozen identity differs')
    variants = {
        ASSIGNMENT + '__probe_1': 'two_cycles',
        ASSIGNMENT + '__probe_2': 'one_cycle',
        ASSIGNMENT + '__yield_wait_for_clearance': 'two_cycles',
        ASSIGNMENT + '__yield_enter_during_occupancy': 'two_cycles',
    }
    if config.get('case_id') not in variants:
        raise ValueError('Exact case identity differs')
    if config.get('rate_hz') != RATE_HZ or config.get('duration_s') != 30:
        raise ValueError('Exact 600-frame capture contract differs')
    cameras = [(c['name'], c['width'], c['height']) for c in config.get('cameras', [])]
    if cameras != list(CAMERAS):
        raise ValueError('Current four-camera profile differs')
    expected = variants[config['case_id']]
    if config.get('case_variant') != expected:
        raise ValueError('Controlled cycle variant differs')
    if config.get('required_atoms') != [] or config.get('source_packets') != []:
        raise ValueError('Unsupported derived atom or packet declaration')
    return {'passed': True, 'case_id': config['case_id'], 'frames': FRAMES,
            'rate_hz': RATE_HZ, 'cameras': [c[0] for c in CAMERAS],
            'source_capture_implemented': True, 'physical_observation_claimed': False}


def request(frame, case, observed):
    """Post-tick brake request from observed state, with no fixture speed claim."""
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError('Frame outside exact capture window')
    if case not in (ASSIGNMENT + '__probe_1', ASSIGNMENT + '__probe_2',
                    ASSIGNMENT + '__yield_wait_for_clearance',
                    ASSIGNMENT + '__yield_enter_during_occupancy'):
        raise ValueError('Unknown exact case')
    if not isinstance(observed, dict) or observed.get('ego_face') != EGO_FACE:
        raise ValueError('Governing observed signal missing')
    target = 1 if case.endswith('probe_2') else 2
    controlled_yield_release = (case.endswith('yield_enter_during_occupancy') and
                                observed['completed_cycles'] >= 2)
    sample = Sample(frame, observed['ego_face'], observed['cross_phase'],
                    observed['speed_mps'], observed['front_to_stop_m'],
                    observed['entered_intersection'], True, False,
                    observed['pedestrians_in_crosswalk'] and not controlled_yield_release,
                    observed['lawful_traffic_conflict'] and not controlled_yield_release)
    return {'brake': commanded_brake(sample, observed['completed_cycles'], target),
            'target_cycles': target, 'command_not_physical_observation': True}


def capture_row(index, frame, elapsed_s, actor, waypoint, signal_state):
    """Extract original Native kinematics and body after a simulator tick."""
    if type(index) is not int or not 0 <= index < FRAMES or type(frame) is not int:
        raise ValueError('Original Native frame identity absent')
    if not isinstance(elapsed_s, (int, float)) or not math.isfinite(elapsed_s):
        raise ValueError('Original Native time absent')
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) != 8 or waypoint is None or not isinstance(signal_state, dict):
        raise ValueError('Original body, lane or signal readback absent')
    return {'video_frame': index, 'native_frame': frame, 'time_s': elapsed_s,
            'source_kind': 'native_observation', 'actor_id': actor.id,
            'blueprint_id': actor.type_id, 'road_id': waypoint.road_id,
            'lane_id': waypoint.lane_id,
            'center_m': [transform.location.x, transform.location.y, transform.location.z],
            'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            'body_vertices_m': [[v.x, v.y, v.z] for v in vertices],
            'signal_readback': signal_state}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config_path = Path(__file__).parent / 'config.json'
    if args.check:
        print(json.dumps(check(json.loads(config_path.read_text())), sort_keys=True))
    elif args.output_dir is not None:
        from live_capture import capture
        print(json.dumps(capture(args.output_dir, config_path, args.host, args.port),
                         sort_keys=True))
    else:
        parser.error('Specify --check or --output-dir')
