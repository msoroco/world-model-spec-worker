"""Native narrow-road person-exposure probe for C136539.

The output is construction-only. It does not establish endangerment or physical
acceptance, and it does not seal a delivery attempt.
"""

import argparse
import json
from pathlib import Path

from exposure_camera import CAMERAS, ExposureCameraCapture, LosslessSourceSink
from exposure_source_capture import ExposureSourceRecorder
from narrow_exposure_route import exposed_position, select_route, speed_control


SUFFIX = '__slow_person_exposure'


def check_config(config):
    if not config.get('selected_case_id', '').endswith(SUFFIX):
        raise ValueError('Unknown exact person-exposure probe case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-600-1b', 'C136539', 'motor_vehicle_driver'):
        raise ValueError('Exposure probe identity differs')
    if (config.get('rate_hz'), config.get('frames'), config.get('requested_speed_mps')) != (20, 80, 2):
        raise ValueError('Exposure probe rate, duration or speed differs')
    if config.get('construction_probe_only') is not True:
        raise ValueError('Exposure probe may not masquerade as delivery')


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
    actors = []
    recorder = pipeline = frame_map = cameras = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_route(world.get_map())
        point = exposed_position(route, waypoint_index=4)
        pedestrian_transform = carla.Transform(carla.Location(*point),
                                                route[4].transform.rotation)
        pedestrian = world.try_spawn_actor(
            world.get_blueprint_library().find('walker.pedestrian.0001'),
            pedestrian_transform)
        if pedestrian is None:
            raise ValueError('Native exposed pedestrian spawn failed')
        actors.append(pedestrian)
        ego = world.try_spawn_actor(
            world.get_blueprint_library().find('vehicle.tesla.model3'),
            route[0].transform)
        if ego is None:
            raise ValueError('Native exposure subject spawn failed')
        actors.append(ego)
        recorder = ExposureSourceRecorder(output, ego, pedestrian, 'pedestrian')
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = ExposureCameraCapture(world, carla, ego, sinks)
        frames = []
        start = None
        for index in range(config['frames']):
            pedestrian.apply_control(carla.WalkerControl(speed=0))
            transform = ego.get_transform()
            position = transform.location
            heading = transform.get_forward_vector()
            velocity = ego.get_velocity()
            target = route[min(2 + index // 8, len(route) - 1)].transform.location
            command = speed_control([position.x, position.y],
                                    [heading.x, heading.y],
                                    [velocity.x, velocity.y],
                                    [target.x, target.y], 2)
            ego.apply_control(carla.VehicleControl(**command))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native exposure snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Native exposure trace/frame mismatch')
            recorder.append(frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-probe.json').write_text(json.dumps({
            'format': 'worker-exposure-construction-probe',
            'case_id': config['selected_case_id'],
            'map_name': world.get_map().name,
            'road_id': route[0].road_id, 'lane_id': route[0].lane_id,
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
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Native exposure world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--config', default='probe-config.json')
    parser.add_argument('--output')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.run:
        if not args.output:
            raise ValueError('Fresh Native exposure output required')
        run(config, args.output, args.host, args.port)


if __name__ == '__main__':
    main()
