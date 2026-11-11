"""Native construction probes for exact nighttime following comparisons.

This records a physical attempt; it does not claim legal or delivery acceptance.
"""

import argparse
import json
from pathlib import Path

from headlamp_camera import CAMERAS, HeadlampCameraCapture, LosslessSourceSink
from headlamp_follow_route import cruise_control, select_follow_route
from headlamp_source_capture import HeadlampSourceRecorder
from headlamp_roadway_capture import RoadwaySourceRecorder


CASE_ID = 'heldout__C178038__NRS-484D-215-2__motor_vehicle_driver__night_299_upper'
CASE_PREFIX = CASE_ID.removesuffix('night_299_upper')
NIGHT_CASES = {
    CASE_PREFIX + 'night_299_upper': (299, True),
    CASE_PREFIX + 'night_299_other': (299, False),
    CASE_PREFIX + 'night_300_upper': (300, True),
    CASE_PREFIX + 'night_301_upper': (301, True),
}


def check_config(config):
    case_id = config.get('selected_case_id')
    if case_id not in NIGHT_CASES:
        raise ValueError('Unknown exact following probe case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484D-215-2', 'C178038', 'motor_vehicle_driver'):
        raise ValueError('Following probe identity differs')
    gap_ft, uppermost = NIGHT_CASES[case_id]
    if (config.get('rate_hz'), config.get('frames'), config.get('requested_gap_ft')) != (20, 80, gap_ft):
        raise ValueError('Following probe rate, duration or gap differs')
    if config.get('requested_uppermost_distribution') is not uppermost:
        raise ValueError('Following probe beam setup differs')
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


def prepare_output(output, config):
    """Accept a fresh standalone directory or the exact runtime materialization."""
    output = Path(output)
    if output.exists():
        if not (output / 'construction.json').is_file():
            raise ValueError('Existing Native output is not a materialized construction')
        config_path = output / 'config.json'
        if not config_path.is_file() or json.loads(config_path.read_text()) != config:
            raise ValueError('Materialized Native config differs')
        if (output / 'trace.jsonl').exists() or (output / 'video_frames.jsonl').exists():
            raise ValueError('Retain prior Native acquisition')
    else:
        output.mkdir(parents=True)
        (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    return output


def run(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    check_config(config)
    output = prepare_output(output, config)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    actors = []
    recorder = roadway = pipeline = frame_map = cameras = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'])
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
        requested_lights = carla.VehicleLightState.Position | carla.VehicleLightState.LowBeam
        if config['requested_uppermost_distribution']:
            requested_lights |= carla.VehicleLightState.HighBeam
        ego.set_light_state(carla.VehicleLightState(requested_lights))
        actual_lights = int(ego.get_light_state())
        if (bool(actual_lights & int(carla.VehicleLightState.HighBeam)) is not
                config['requested_uppermost_distribution'] or
                not actual_lights & int(carla.VehicleLightState.LowBeam)):
            raise ValueError('Native beam setup readback failed')
        recorder = HeadlampSourceRecorder(output, ego, lead)
        roadway = RoadwaySourceRecorder(output, world, ego, carla)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
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
            roadway.append(frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-probe.json').write_text(json.dumps({
            'format': 'worker-headlamp-construction-probe',
            'case_id': config['selected_case_id'],
            'map_name': world.get_map().name,
            'road_id': route['ego'].road_id, 'lane_id': route['ego'].lane_id,
            'requested_gap_ft': config['requested_gap_ft'],
            'requested_uppermost_distribution': config['requested_uppermost_distribution'],
            'frames': frames,
            'lighting_time_physical_verification': False,
            'roadway_occupancy_physical_verification': False,
            'delivery_ready': False}, indent=2) + '\n')
    finally:
        if frame_map is not None:
            frame_map.close()
        if recorder is not None:
            recorder.close()
        if roadway is not None:
            roadway.close()
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
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output', '--output-dir', dest='output')
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
