"""CARLA-lazy Native construction for an opposing-direction left-turn comparison.

The selected cell/case identity is supplied by the eventual compatible binding.
This module only constructs and records the physical attempt; it makes no legal
or physical-completion claim.
"""

import argparse
import json
from pathlib import Path

from ending_road_camera import CAMERAS, EndingRoadCameraCapture, LosslessSourceSink
from ending_road_runner import conflict_polygon, control_to_waypoint, extend_exit
from opposing_left_control import turn_release_step
from opposing_left_route import select_opposing_left_routes
from opposing_left_source import context_from_native, OpposingLeftSourceRecorder


def check_config(config):
    if config.get('law_id') != 'NRS-484B-250-3' or config.get('actor') != 'motor_vehicle_driver':
        raise ValueError('Opposing-left law or actor differs')
    if not isinstance(config.get('selected_case_id'), str) or not config['selected_case_id'].endswith('__opposing_left_turn'):
        raise ValueError('Opposing-left exact case identity differs')
    if config.get('cell_id') not in ('C293604',):
        raise ValueError('Opposing-left case requires compatible left-turn cell binding')
    if config.get('rate_hz') != 20 or config.get('frames', 0) < 80:
        raise ValueError('Opposing-left capture requires at least four seconds at 20 Hz')
    if [c.get('name') for c in config.get('cameras', [])] != list(CAMERAS) or any(
            [c.get('width'), c.get('height')] != list(CAMERAS[c['name']][2])
            for c in config['cameras']):
        raise ValueError('Opposing-left four-camera profile differs')


def run(config, output, host='127.0.0.1', port=2000):
    check_config(config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    originals = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
                 'trace.jsonl', 'video_frames.jsonl')
    if any((output / name).exists() for name in originals):
        raise FileExistsError('Retain prior opposing-left original acquisition')
    config_path = output / 'config.json'
    if config_path.exists():
        if json.loads(config_path.read_text()) != config:
            raise ValueError('Materialized opposing-left config differs')
    else:
        config_path.write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original_settings = world.get_settings()
    actors, sinks = [], {}
    cameras = recorder = pipeline = frame_map = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        routes = select_opposing_left_routes(world.get_map())
        turning_path = extend_exit(routes['turning'])
        opposite_path = extend_exit(routes['opposite'])
        routes['turning'], routes['opposite'] = turning_path, opposite_path
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        turning = world.try_spawn_actor(blueprint, turning_path[0].transform)
        if turning is None:
            raise ValueError('Opposing-left turning actor spawn failed')
        actors.append(turning)
        opposite = world.try_spawn_actor(blueprint, opposite_path[0].transform)
        if opposite is None:
            raise ValueError('Opposing-left opposite actor spawn failed')
        actors.append(opposite)
        polygon = conflict_polygon(turning_path, opposite_path)
        context = context_from_native(routes, turning, opposite)
        recorder = OpposingLeftSourceRecorder(output, context, turning, opposite)
        pipeline = PipelineCapture(client, turning, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = EndingRoadCameraCapture(world, carla, turning, sinks)
        frames, start = [], None
        state = {'opposite_seen_in_zone': False, 'turning_released': False}
        for _ in range(config['frames']):
            state = turn_release_step(opposite, polygon,
                    opposite_seen_in_zone=state['opposite_seen_in_zone'],
                    turning_released=state['turning_released'])
            turning.apply_control(carla.VehicleControl(**control_to_waypoint(
                turning, turning_path[-1], state['turning_speed_mps'])))
            opposite.apply_control(carla.VehicleControl(**control_to_waypoint(
                opposite, opposite_path[-1], state['opposite_speed_mps'])))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Opposing-left Native frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if (trace.get('frame'), trace.get('time_s')) != (frame, time_s):
                raise ValueError('Opposing-left trace/frame mismatch')
            recorder.append(frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'opposing_left_construction_observation.json').write_text(json.dumps({
            'format': 'worker-opposing-left-construction-observation',
            'case_id': config['selected_case_id'], 'map_name': routes['map_name'],
            'frames': frames, 'opposite_seen_in_zone': state['opposite_seen_in_zone'],
            'turning_released': state['turning_released'],
            'physical_completion_claimed': False}, indent=2) + '\n')
    finally:
        if frame_map is not None: frame_map.close()
        if recorder is not None: recorder.close()
        if pipeline is not None: pipeline.close(confirmed=False)
        if cameras is not None: cameras.close()
        for sink in sinks.values(): sink.close()
        for actor in reversed(actors): actor.destroy()
        world.apply_settings(original_settings)
        restored = world.get_settings()
        if (restored.synchronous_mode != original_settings.synchronous_mode or
                restored.fixed_delta_seconds != original_settings.fixed_delta_seconds):
            raise ValueError('Opposing-left world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if not args.check:
        if not args.output_dir:
            raise ValueError('Fresh Native output directory required')
        run(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
