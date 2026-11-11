"""Exact overtaking delivery construction; physical outcome remains unverified."""

import argparse
import json
from pathlib import Path

from overtake_camera import CAMERAS, OvertakeCameraCapture, LosslessSourceSink
from overtake_route import choose_target, select_overtake_route, steer_speed_control
from overtake_variants import left_target_xy
from overtake_source_capture import OvertakeSourceRecorder


CASE_ID = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__left_pass_wide'
ALL_CASE_IDS = [
    'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__' + suffix
    for suffix in ('left_pass_wide', 'left_pass_narrow',
                   'return_before_clear', 'return_after_clear')
]


def check_config(config):
    if config.get('selected_case_id') != CASE_ID:
        raise ValueError('Unknown exact overtaking probe case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-207-1', 'C110161', 'motor_vehicle_driver'):
        raise ValueError('Overtake probe identity differs')
    if (config.get('rate_hz'), config.get('frames'), config.get('requested_return_clearance_m')) != (20, 160, 3):
        raise ValueError('Overtake probe rate, duration or return clearance differs')
    if config.get('duration_s') != 8 or config.get('supported_case_ids') not in ([CASE_ID], ALL_CASE_IDS):
        raise ValueError('Overtake delivery duration or selected case differs')
    if config.get('construction_probe_only') is not None:
        raise ValueError('Delivery config retains construction-probe marker')


def _drive(actor, target, speed, target_xy=None):
    transform = actor.get_transform()
    position = transform.location
    heading = transform.get_forward_vector()
    velocity = actor.get_velocity()
    destination = target.transform.location
    if target_xy is None:
        target_xy = [destination.x, destination.y]
    return steer_speed_control([position.x, position.y], [heading.x, heading.y],
                               [velocity.x, velocity.y],
                               target_xy, target_speed_mps=speed)


def _longitudinal(row):
    hx, hy = row['road_tangent_xy']
    ego = [x * hx + y * hy for x, y in row['ego_corners']]
    other = [x * hx + y * hy for x, y in row['other_corners']]
    left_x, left_y = -hy, hx
    ego_left = [x * left_x + y * left_y for x, y in row['ego_corners']]
    other_left = [x * left_x + y * left_y for x, y in row['other_corners']]
    abreast_left = (min(ego) <= max(other) and min(other) <= max(ego) and
                    min(ego_left) > max(other_left))
    return min(ego), max(other), abreast_left


def prepare_output(config, output):
    check_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / 'config.json'
    if config_path.exists():
        if json.loads(config_path.read_text()) != config:
            raise ValueError('Materialized overtake config differs from selected case')
    else:
        config_path.write_text(json.dumps(config, indent=2) + '\n')
    if any((output / name).exists() for name in
           ('trace.jsonl', 'participant_footprints.jsonl', 'video_frames.jsonl')):
        raise ValueError('Retain prior Native overtake acquisition')
    return output


def run(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    output = prepare_output(config, output)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    actors = []
    recorder = pipeline = frame_map = cameras = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_overtake_route(world.get_map())
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        other = world.try_spawn_actor(blueprint, route['right'][8].transform)
        if other is None:
            raise ValueError('Native overtaken vehicle spawn failed')
        actors.append(other)
        ego = world.try_spawn_actor(blueprint, route['right'][0].transform)
        if ego is None:
            raise ValueError('Native overtaking subject spawn failed')
        actors.append(ego)
        recorder = OvertakeSourceRecorder(output, ego, other, world.get_map())
        pipeline = PipelineCapture(client, ego, output, CASE_ID,
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = OvertakeCameraCapture(world, carla, ego, sinks)
        frames = []
        start = None
        passed_abreast = False
        ego_rear, other_front = -1e9, 1e9
        last_row = None
        for index in range(config['frames']):
            position = ego.get_transform().location
            target = choose_target(route, [position.x, position.y],
                                   ego_rear, other_front,
                                   passed_abreast=passed_abreast,
                                   requested_return_clearance_m=3)
            target_xy = None
            if target['phase'] == 'pass_left' and last_row is not None:
                target_xy = left_target_xy(target['waypoint'], last_row,
                                           config['target_left_gap_m'])
            ego.apply_control(carla.VehicleControl(**_drive(
                ego, target['waypoint'], 8, target_xy)))
            other.apply_control(carla.VehicleControl(**_drive(
                other, route['right'][min(11 + index // 6, len(route['right']) - 1)], 4)))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native overtake snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Native overtake trace/frame mismatch')
            row = recorder.append(frame, time_s)
            last_row = row
            ego_rear, other_front, abreast = _longitudinal(row)
            passed_abreast = passed_abreast or abreast
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-observation.json').write_text(json.dumps({
            'format': 'worker-overtake-construction-observation', 'case_id': CASE_ID,
            'map_name': world.get_map().name, 'road_id': route['road_id'],
            'right_lane_id': route['right_lane_id'],
            'left_lane_id': route['left_lane_id'], 'frames': frames,
            'abreast_observed': passed_abreast,
            'delivery_ready': False}, indent=2) + '\n')
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
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Native overtake world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir', '--output', dest='output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.run:
        if not args.output:
            raise ValueError('Fresh Native overtake output required')
        run(config, args.output, args.host, args.port)


if __name__ == '__main__':
    main()
