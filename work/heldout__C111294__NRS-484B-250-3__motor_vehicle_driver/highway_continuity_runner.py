"""CARLA-lazy construction for a controlled highway-continuity comparison.

This prospective runner captures one configured category at a time. The two
attempts must be independently reviewed for equivalent geometry and timing;
selection alone cannot establish legal highway identity or physical success.
"""

import argparse
import json
from pathlib import Path

from categorical_highway_points import select_controlled_pair
from ending_road_camera import CAMERAS, EndingRoadCameraCapture, LosslessSourceSink
from ending_road_control_inventory import ungoverned_route_pair, original_ungoverned_inventory
from ending_road_runner import (choose_control_targets, conflict_polygon,
                                control_to_waypoint, extend_exit)
from highway_continuity_source import ContinuitySourceRecorder, topology_from_pair
from native_pair_preflight import select_bound_pair

ASSIGNMENT = 'heldout__C111294__NRS-484B-250-3__motor_vehicle_driver'
CASE = ASSIGNMENT + '__continuing_highway'


def check_config(config):
    if (config.get('selected_case_id'), config.get('law_id'), config.get('cell_id'),
            config.get('actor')) != (CASE, 'NRS-484B-250-3', 'C111294',
                                     'motor_vehicle_driver'):
        raise ValueError('Highway-continuity exact identity differs')
    if config.get('subject_category') != 'continuing':
        raise ValueError('Highway-continuity runner requires continuing point')
    if config.get('rate_hz') != 20 or config.get('frames', 0) < 80:
        raise ValueError('Highway-continuity capture needs at least four seconds at 20 Hz')
    if config.get('yield_clearance_m', 0) <= 0:
        raise ValueError('Highway-continuity clearance must be positive')
    cameras = config.get('cameras', [])
    if [camera.get('name') for camera in cameras] != list(CAMERAS) or any(
            [camera.get('width'), camera.get('height')] != list(CAMERAS[camera['name']][2])
            for camera in cameras):
        raise ValueError('Highway-continuity source cameras differ from profile')


def select_native_pair(world_map, lights, *, max_spawns=300):
    pair = select_controlled_pair(
        world_map, max_spawns=max_spawns,
        route_accept=lambda subject, other: ungoverned_route_pair(subject, other, lights))
    pair = dict(pair)
    for name in ('ending', 'continuing', 'other'):
        pair[name] = extend_exit(pair[name])
    return pair


def run(config, output, host='127.0.0.1', port=2000, expected_pair=None):
    check_config(config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    original_files = ('highway_pair_topology.json', 'intersection_participants.jsonl',
                      'trace.jsonl', 'video_frames.jsonl', 'control_inventory.json',
                      'controlled_route_pair.json')
    if any((output / name).exists() for name in original_files):
        raise FileExistsError('Retain prior original highway-continuity acquisition')
    config_path = output / 'config.json'
    if config_path.exists():
        if json.loads(config_path.read_text()) != config:
            raise ValueError('Materialized highway-continuity config differs')
    else:
        config_path.write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    actors, sinks = [], {}
    cameras = recorder = pipeline = frame_map = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        lights = list(world.get_actors().filter('traffic.traffic_light*'))
        if expected_pair is None:
            raise ValueError('Expected controlled Native route-pair binding is required')
        pair, binding = select_bound_pair(world.get_map(), lights,
            max_spawns=config.get('max_spawns', 300), expected=expected_pair)
        (output / 'controlled_route_pair.json').write_text(
            json.dumps(binding, indent=2, allow_nan=False) + '\n')
        for name in ('ending', 'continuing', 'other'):
            pair[name] = extend_exit(pair[name])
        subject_path, other_path = pair['continuing'], pair['other']
        inventory = original_ungoverned_inventory(
            {'path': subject_path, 'junction_id': pair['junction_id']},
            {'path': other_path, 'junction_id': pair['junction_id']}, lights)
        (output / 'control_inventory.json').write_text(
            json.dumps(inventory, indent=2, allow_nan=False) + '\n')
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        subject = world.try_spawn_actor(blueprint, subject_path[0].transform)
        if subject is None:
            raise ValueError('Continuing-highway subject spawn failed')
        actors.append(subject)
        other = world.try_spawn_actor(blueprint, other_path[0].transform)
        if other is None:
            raise ValueError('Fixed through-highway actor spawn failed')
        actors.append(other)
        polygon = conflict_polygon(subject_path, other_path)
        topology = topology_from_pair(pair, 'continuing', subject, other, polygon)
        recorder = ContinuitySourceRecorder(output, topology, subject, other)
        pipeline = PipelineCapture(client, subject, output, CASE,
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = EndingRoadCameraCapture(world, carla, subject, sinks)
        routes = {'subject': subject_path, 'other': other_path,
                  'conflict_polygon_xy': polygon, 'other_seen_in_zone': False}
        frames, start, released = [], None, False
        for _ in range(config['frames']):
            subject_target, other_target, go = choose_control_targets(
                subject, other, routes, released, config['yield_clearance_m'])
            released = go
            subject.apply_control(carla.VehicleControl(**control_to_waypoint(
                subject, subject_target, 5 if go else 0)))
            other.apply_control(carla.VehicleControl(**control_to_waypoint(
                other, other_target, 5)))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Highway-continuity Native frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Highway-continuity trace/frame mismatch')
            recorder.append(frame, time_s)
            x, y = other.get_transform().location.x, other.get_transform().location.y
            xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
            routes['other_seen_in_zone'] = routes['other_seen_in_zone'] or (
                min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys))
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-observation.json').write_text(json.dumps({
            'format': 'worker-highway-continuity-construction-observation',
            'case_id': CASE, 'map_name': pair['map_name'], 'frames': frames,
            'through_seen_in_zone': routes['other_seen_in_zone'],
            'subject_released': released, 'physical_completion_claimed': False},
            indent=2) + '\n')
    finally:
        if frame_map is not None: frame_map.close()
        if recorder is not None: recorder.close()
        if pipeline is not None: pipeline.close(confirmed=False)
        if cameras is not None: cameras.close()
        for sink in sinks.values(): sink.close()
        for actor in reversed(actors): actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Highway-continuity world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--expected-pair')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if not args.check:
        if not args.output_dir:
            raise ValueError('Fresh Native output directory required')
        if not args.expected_pair:
            raise ValueError('--expected-pair is required for Native capture')
        run(config, args.output_dir, args.host, args.port,
            json.loads(Path(args.expected_pair).read_text()))


if __name__ == '__main__':
    main()
