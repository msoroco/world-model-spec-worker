"""Native construction runner for all six exact C136539 exposure scenes.

This captures original sources only; saved processing and physical review follow.
"""

import argparse
import json
from pathlib import Path

from exposure_camera import CAMERAS, ExposureCameraCapture, LosslessSourceSink
from exposure_source_capture import ExposureSourceRecorder
from narrow_exposure_route import select_route, speed_control
from exposure_case_setup import case_settings, spawn_exposed


def check_config(config):
    return case_settings(config)


def run(config, output, host, port):
    import carla  # Native-only dependency.
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    exact = check_config(config)
    output = Path(output)
    if not output.is_dir() or json.loads((output / 'config.json').read_text()) != config:
        raise ValueError('Materialized exposure attempt/config mismatch')
    if (output / 'exposed_actor_footprints.jsonl').exists():
        raise ValueError('Retain prior original exposure attempt')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    actors = []
    recorder = pipeline = frame_map = cameras = None
    sinks = {}
    frames = []
    completed = False
    route_identity = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_route(world.get_map(), steps=40)
        exposed = spawn_exposed(world, carla, route, exact)
        actors.append(exposed)
        ego = world.try_spawn_actor(
            world.get_blueprint_library().find('vehicle.tesla.model3'),
            route[0].transform)
        if ego is None:
            raise ValueError('Native exposure subject spawn failed')
        actors.append(ego)
        recorder = ExposureSourceRecorder(output, ego, exposed, exact['exposed_kind'])
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = ExposureCameraCapture(world, carla, ego, sinks)
        route_identity = {'map_name': world.get_map().name,
                          'road_id': route[0].road_id, 'lane_id': route[0].lane_id}
        start = None
        for index in range(config['frames']):
            if exact['exposed_kind'] == 'pedestrian':
                exposed.apply_control(carla.WalkerControl(speed=0))
            transform = ego.get_transform()
            position = transform.location
            heading = transform.get_forward_vector()
            velocity = ego.get_velocity()
            target = route[min(4 + index // 4, len(route) - 1)].transform.location
            command = speed_control([position.x, position.y],
                                    [heading.x, heading.y],
                                    [velocity.x, velocity.y],
                                    [target.x, target.y], exact['speed_mps'])
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
            'frames': frames, 'exact_settings': exact, 'delivery_ready': False}, indent=2) + '\n')
        completed = True
    finally:
        if frame_map is not None:
            frame_map.close()
        if recorder is not None:
            recorder.close()
        if pipeline is not None:
            pipeline.close(confirmed=completed)
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
        if completed:
            seal_capture(output, frames=frames,
                         restoration={'restored': True,
                                      'synchronous_mode': original.synchronous_mode,
                                      'fixed_delta_seconds': original.fixed_delta_seconds},
                         errors=[], encoder_exit_codes={name: 0 for name in sinks},
                         context={'route': route_identity,
                                  'exact_settings': exact,
                                  'source': 'original Native construction observation'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--config', default='cases/slow_person_exposure.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.output_dir:
        run(config, args.output_dir, args.host, args.port)
    elif args.run:
        raise ValueError('Materialized exposure output required')


if __name__ == '__main__':
    main()
