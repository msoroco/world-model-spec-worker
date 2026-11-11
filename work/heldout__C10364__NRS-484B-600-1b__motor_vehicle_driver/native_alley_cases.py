"""CARLA-lazy capture for exact C10364 alley construction cases."""

import argparse
import json
from pathlib import Path

from alley_camera import CAMERAS, AlleyCameraCapture, LosslessSourceSink
from alley_case_setup import case_settings, participant_positions, verify_polygon_source
from alley_route import control_step, select_alley_route
from alley_source_capture import AlleySourceRecorder


def check_config(config):
    return case_settings(config)


def run(config, output, host, port):
    import carla  # Native-only dependency.
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    exact = check_config(config)
    output = Path(output)
    if not output.is_dir() or json.loads((output / 'config.json').read_text()) != config:
        raise ValueError('Materialized alley attempt/config mismatch')
    verify_polygon_source(exact, output)
    if (output / 'participant_footprints.jsonl').exists():
        raise ValueError('Retain prior original alley attempt')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    previous = world.get_settings()
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
        route = select_alley_route(
            world.get_map(), exact['polygon_xy'],
            direction=exact['direction'],
            polygon_source=exact['polygon_source']['path'],
            minimum_steps=12)
        placement = participant_positions(route, alley_width_m=exact['alley_width_m'],
                                          pedestrian_offset_m=exact['pedestrian_offset_m'])
        library = world.get_blueprint_library()
        person = world.try_spawn_actor(library.find('walker.pedestrian.0001'),
            carla.Transform(carla.Location(x=placement.pedestrian.x,
                                           y=placement.pedestrian.y,
                                           z=route[4].transform.location.z),
                            route[4].transform.rotation))
        if person is None:
            raise ValueError('Native alley pedestrian spawn failed')
        actors.append(person)
        prop = world.try_spawn_actor(library.find('vehicle.tesla.model3'),
            carla.Transform(carla.Location(x=placement.property_center.x,
                                           y=placement.property_center.y,
                                           z=route[6].transform.location.z),
                            route[6].transform.rotation))
        if prop is None:
            raise ValueError('Native alley property object spawn failed')
        prop.set_simulate_physics(False)
        actors.append(prop)
        ego = world.try_spawn_actor(library.find('vehicle.tesla.model3'),
                                    route[0].transform)
        if ego is None:
            raise ValueError('Native alley subject spawn failed')
        actors.append(ego)
        recorder = AlleySourceRecorder(output, ego, person, prop)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = AlleyCameraCapture(world, carla, ego, sinks,
            overview_height_delta_m=exact['overview_height_delta_m'])
        route_identity = {'map_name': world.get_map().name,
                          'road_id': route[0].road_id,
                          'lane_id': route[0].lane_id,
                          'polygon_source': exact['polygon_source']}
        start = None
        for index in range(config['frames']):
            person.apply_control(carla.WalkerControl(speed=0))
            transform = ego.get_transform()
            position = transform.location
            heading = transform.get_forward_vector()
            velocity = ego.get_velocity()
            target = route[min(exact['route_lookahead_steps'] + index // 4,
                               len(route)-1)].transform.location
            command = control_step((position.x, position.y),
                (heading.x, heading.y), (velocity.x, velocity.y),
                (target.x, target.y), target_speed_mps=exact['speed_mps'])
            ego.apply_control(carla.VehicleControl(**command))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native alley snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Native alley trace/frame mismatch')
            recorder.append(frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-probe.json').write_text(json.dumps({
            'format': 'worker-alley-construction-probe',
            'case_id': config['selected_case_id'],
            'route': route_identity, 'frames': frames,
            'requested_settings': exact, 'delivery_ready': False}, indent=2) + '\n')
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
        world.apply_settings(previous)
        restored = world.get_settings()
        if (restored.synchronous_mode != previous.synchronous_mode or
                restored.fixed_delta_seconds != previous.fixed_delta_seconds):
            raise ValueError('Native alley settings restore failed')
        if completed:
            seal_capture(output, frames=frames,
                         restoration={'restored': True,
                                      'synchronous_mode': previous.synchronous_mode,
                                      'fixed_delta_seconds': previous.fixed_delta_seconds},
                         errors=[], encoder_exit_codes={name: 0 for name in sinks},
                         context={'route': route_identity,
                                  'requested_settings': exact,
                                  'source': 'original Native construction observation'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.run:
        if not args.output_dir:
            raise ValueError('Native alley run needs an output directory')
        run(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
