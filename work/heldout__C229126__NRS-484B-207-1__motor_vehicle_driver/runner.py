"""Prospective Native pass acquisition for the C229126 exact cases.

This module is importable without CARLA.  A real run remains subject to
independent physical and pixel review after saved processing.
"""

import argparse
import json
from pathlib import Path

from native_scene import build_scene, destroy_scene
from overtake_camera import CAMERAS, LosslessSourceSink, OvertakeCameraCapture
from overtake_controller import TARGETS
from overtake_route import case_target, steer_speed_control
from overtake_source_capture import OvertakeSourceRecorder


PREFIX = 'heldout__C229126__NRS-484B-207-1__motor_vehicle_driver__'


def check_config(config):
    case_id = config.get('selected_case_id')
    if not isinstance(case_id, str) or not case_id.startswith(PREFIX):
        raise ValueError('Wrong exact C229126 case identity')
    suffix = case_id[len(PREFIX):]
    if suffix not in TARGETS or (config.get('law_id'), config.get('cell_id'),
                                  config.get('actor')) != (
            'NRS-484B-207-1', 'C229126', 'motor_vehicle_driver'):
        raise ValueError('Wrong C229126 law, cell, actor or variant')
    if (config.get('target_left_gap_m'),
            config.get('requested_return_clearance_m')) != TARGETS[suffix]:
        raise ValueError('Exact comparison controls changed')
    if config.get('rate_hz') != 20 or config.get('frames') != 320 or config.get('duration_s') != 16:
        raise ValueError('C229126 source duration or 20 Hz rate changed')
    if set(config.get('camera_names', [])) != set(CAMERAS):
        raise ValueError('Four named original source cameras required')
    if case_id not in config.get('supported_case_ids', []):
        raise ValueError('Exact case missing from supported case list')
    return suffix


def _control(actor, waypoint, target_xy, speed_mps):
    transform = actor.get_transform()
    location = transform.location
    heading = transform.get_forward_vector()
    velocity = actor.get_velocity()
    if target_xy is None:
        target = waypoint.transform.location
        target_xy = [target.x, target.y]
    return steer_speed_control([location.x, location.y], [heading.x, heading.y],
                               [velocity.x, velocity.y], target_xy,
                               target_speed_mps=speed_mps)


def _abreast(row):
    hx, hy = row['road_tangent_xy']
    ego = [x * hx + y * hy for x, y in row['ego_corners']]
    other = [x * hx + y * hy for x, y in row['other_corners']]
    lx, ly = -hy, hx
    ego_left = [x * lx + y * ly for x, y in row['ego_corners']]
    other_left = [x * lx + y * ly for x, y in row['other_corners']]
    return min(ego) <= max(other) and min(other) <= max(ego) and min(ego_left) > max(other_left)


def run(config, output, host, port):
    suffix = check_config(config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in
           ('config.json', 'trace.jsonl', 'participant_footprints.jsonl',
            'video_frames.jsonl')):
        raise ValueError('Retain prior Native pass acquisition')
    (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original_settings = world.get_settings()
    scene = recorder = pipeline = frame_map = cameras = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        scene = build_scene(world)
        ego, other, route = scene['ego'], scene['other'], scene['route']
        recorder = OvertakeSourceRecorder(output, ego, other, world.get_map())
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = OvertakeCameraCapture(world, carla, ego, sinks)
        observed_frames = []
        first_time = None
        previous_row = None
        passed_abreast = False
        for index in range(config['frames']):
            position = ego.get_transform().location
            if previous_row is None:
                waypoint = route['left'][3]
                target_xy = None
            else:
                selected = case_target(route, suffix, [position.x, position.y],
                                       previous_row, passed_abreast=passed_abreast)
                waypoint, target_xy = selected['waypoint'], selected['target_xy']
            ego.apply_control(carla.VehicleControl(**_control(ego, waypoint, target_xy, 8)))
            other_waypoint = route['right'][min(11 + index // 6, len(route['right']) - 1)]
            other.apply_control(carla.VehicleControl(**_control(other, other_waypoint, None, 4)))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native pass snapshot/frame mismatch')
            if first_time is None:
                first_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - first_time
            trace = pipeline.capture(frame, time_s)
            if (trace.get('frame'), trace.get('time_s')) != (frame, time_s):
                raise ValueError('Native pass trace/frame mismatch')
            row = recorder.append(frame, time_s)
            passed_abreast = passed_abreast or _abreast(row)
            previous_row = row
            frame_map.append(frame, time_s)
            observed_frames.append(frame)
        cameras.verify(observed_frames)
        (output / 'construction-observation.json').write_text(json.dumps({
            'format': 'worker-c229126-construction-observation',
            'case_id': config['selected_case_id'],
            'map_name': world.get_map().name,
            'road_id': route['road_id'],
            'right_lane_id': route['right_lane_id'],
            'left_lane_id': route['left_lane_id'],
            'frames': observed_frames,
            'abreast_observed': passed_abreast,
            'physical_acceptance_claimed': False,
        }, indent=2) + '\n')
    finally:
        if frame_map is not None:
            frame_map.close()
        if recorder is not None:
            recorder.close()
        if pipeline is not None:
            pipeline.close(confirmed=False)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        if scene is not None:
            destroy_scene(scene)
        world.apply_settings(original_settings)
        restored = world.get_settings()
        if (restored.synchronous_mode != original_settings.synchronous_mode or
                restored.fixed_delta_seconds != original_settings.fixed_delta_seconds):
            raise ValueError('Native pass world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--output-dir', '--output', dest='output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.run:
        if not args.output:
            raise ValueError('Fresh Native pass output required')
        run(config, args.output, args.host, args.port)


if __name__ == '__main__':
    main()
