"""Native posted one-way construction probe for C125714.

This probe does not seal a delivery attempt or establish median-opening
geometry, legal sufficient width, or a statutory exception.
"""

import argparse
import json
from pathlib import Path

from right_half_route import control_step
from one_way_construction import select_one_way_route, spawn_one_way_sign
from one_way_source_capture import OneWaySourceRecorder
from left_excursion_target import pinned_subject_waypoint, target_xy
from right_half_camera import CAMERAS, LosslessSourceSink, RightHalfCameraCapture


CASE_ID = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__posted_one_way'


def check_config(config):
    case_id = config.get('selected_case_id', '')
    if case_id != CASE_ID:
        raise ValueError('Unknown one-way probe case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-200-1', 'C125714', 'motor_vehicle_driver'):
        raise ValueError('Right-half probe identity differs')
    if config.get('rate_hz') != 20 or config.get('frames', 0) < 80:
        raise ValueError('Right-half probe requires at least 80 frames at 20 Hz')
    if config.get('travel_direction') != 'east':
        raise ValueError('One-way probe requires eastbound travel')
    if config.get('requested_lane_fraction') != .75:
        raise ValueError('Exact left-excursion controller fraction differs')
    if config.get('construction_probe_only') is not True:
        raise ValueError('Probe may not masquerade as delivery')


def run(config, output, host, port):
    import carla  # Native-only dependency.
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    check_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    owned = []
    recorder = cameras = pipeline = frame_map = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_one_way_route(world.get_map(), direction=config['travel_direction'])
        ego = world.try_spawn_actor(
            world.get_blueprint_library().find('vehicle.tesla.model3'),
            route[0].transform)
        if ego is None:
            raise ValueError('Native right-half subject spawn failed')
        owned.append(ego)
        sign = spawn_one_way_sign(world, carla, route[0])
        owned.append(sign)
        recorder = OneWaySourceRecorder(output, ego, sign)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = RightHalfCameraCapture(world, carla, ego, sinks)
        frames = []
        start = None
        for index in range(config['frames']):
            transform = ego.get_transform()
            position = transform.location
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            target_waypoint = route[min(2 + index // 8, len(route) - 1)]
            target = target_xy(target_waypoint, frame_index=index,
                               requested_fraction=config['requested_lane_fraction'])
            command = control_step([position.x, position.y],
                                   [forward.x, forward.y], [velocity.x, velocity.y],
                                   target)
            ego.apply_control(carla.VehicleControl(**command))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native right-half snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            waypoint = pinned_subject_waypoint(world.get_map(), ego.get_location(),
                                               route[0])
            trace = pipeline.capture(frame, snapshot.timestamp.elapsed_seconds - start)
            if trace.get('frame') != frame or trace.get('time_s') != snapshot.timestamp.elapsed_seconds - start:
                raise ValueError('Native right-half trace/frame mismatch')
            recorder.append(frame, snapshot.timestamp.elapsed_seconds - start,
                            waypoint)
            frame_map.append(frame, snapshot.timestamp.elapsed_seconds - start)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-probe.json').write_text(json.dumps({
            'format': 'worker-one-way-construction-probe',
            'case_id': config['selected_case_id'],
            'map_name': world.get_map().name,
            'road_id': route[0].road_id, 'lane_id': route[0].lane_id,
            'sign_actor_id': str(sign.id), 'designation_verified': False,
            'frames': frames, 'delivery_ready': False}, indent=2) + '\n')
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
        for actor in reversed(owned):
            actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Native right-half world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--config', default='one-way-probe-config.json')
    parser.add_argument('--output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.run:
        if not args.output:
            raise ValueError('Fresh Native output directory required')
        run(config, args.output, args.host, args.port)


if __name__ == '__main__':
    main()
