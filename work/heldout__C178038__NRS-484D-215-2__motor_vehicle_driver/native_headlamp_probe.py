"""Native construction probe for the 299-foot nighttime upper-beam case.

This records a physical attempt; it does not claim legal or delivery acceptance.
"""

import argparse
import json
from pathlib import Path

from headlamp_camera import CAMERAS, HeadlampCameraCapture, LosslessSourceSink
from headlamp_follow_route import cruise_control, select_follow_route
from headlamp_source_capture import HeadlampSourceRecorder


CASE_ID = 'heldout__C178038__NRS-484D-215-2__motor_vehicle_driver__night_299_upper'


def check_config(config):
    if config.get('selected_case_id') != CASE_ID:
        raise ValueError('Unknown exact following probe case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484D-215-2', 'C178038', 'motor_vehicle_driver'):
        raise ValueError('Following probe identity differs')
    if (config.get('rate_hz'), config.get('frames'), config.get('requested_gap_ft')) != (20, 80, 299):
        raise ValueError('Following probe rate, duration or gap differs')
    if config.get('construction_probe_only') is not True:
        raise ValueError('Following probe may not masquerade as delivery')


def _command(actor, target, speed=6):
    transform = actor.get_transform()
    location = transform.location
    heading = transform.get_forward_vector()
    velocity = actor.get_velocity()
    destination = target.transform.location
    return cruise_control([location.x, location.y], [heading.x, heading.y],
                          [velocity.x, velocity.y], [destination.x, destination.y],
                          target_speed_mps=speed)


def run(config, output, host, port):
    import carla
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
        route = select_follow_route(world.get_map(), target_gap_ft=299)
        library = world.get_blueprint_library()
        lead = world.try_spawn_actor(library.find('vehicle.tesla.model3'),
                                     route['lead'].transform)
        if lead is None:
            raise ValueError('Native following lead spawn failed')
        actors.append(lead)
        ego = world.try_spawn_actor(library.find('vehicle.tesla.model3'),
                                    route['ego'].transform)
        if ego is None:
            raise ValueError('Native following subject spawn failed')
        actors.append(ego)
        ego.set_light_state(carla.VehicleLightState(carla.VehicleLightState.Position |
                                                    carla.VehicleLightState.LowBeam |
                                                    carla.VehicleLightState.HighBeam))
        if not int(ego.get_light_state()) & int(carla.VehicleLightState.HighBeam):
            raise ValueError('Native upper-beam setup readback failed')
        recorder = HeadlampSourceRecorder(output, ego, lead)
        pipeline = PipelineCapture(client, ego, output, CASE_ID,
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = HeadlampCameraCapture(world, carla, ego, sinks)
        frames = []
        start = None
        for index in range(config['frames']):
            lead.apply_control(carla.VehicleControl(**_command(
                lead, route['chain'][min(route['lead_index'] + 3 + index // 8,
                                         len(route['chain']) - 1)])))
            ego.apply_control(carla.VehicleControl(**_command(
                ego, route['chain'][min(3 + index // 8, len(route['chain']) - 1)])))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native following snapshot/frame mismatch')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Native following trace/frame mismatch')
            recorder.append(frame, time_s, carla)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-probe.json').write_text(json.dumps({
            'format': 'worker-headlamp-construction-probe', 'case_id': CASE_ID,
            'map_name': world.get_map().name,
            'road_id': route['ego'].road_id, 'lane_id': route['ego'].lane_id,
            'requested_gap_ft': 299, 'frames': frames,
            'lighting_time_physical_verification': False,
            'roadway_occupancy_physical_verification': False,
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
            raise ValueError('Native following world settings restore failed')


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
            raise ValueError('Fresh Native following output required')
        run(config, args.output, args.host, args.port)


if __name__ == '__main__':
    main()
