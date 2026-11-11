"""Prospective two-vehicle Native capture for the rear opposing-left-turn case.

The module imports CARLA only inside run(). Physical crossing order, source
pixels and official-device applicability remain independent local checks.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree

from opposing_turn_control import command_pair
from opposing_turn_native_routes import choose_native_pair
from opposing_turn_sources import OpposingTurnRecorder


ASSIGNMENT = 'heldout__C109749__NRS-484B-400-2c__motor_vehicle_driver'
PRIMARY = ASSIGNMENT + '__rear_pass_no_device'
CAMERA_NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-400-2c', 'C109749', 'motor_vehicle_driver'):
        raise ValueError('wrong frozen opposing-left-turn scope')
    if config.get('selected_case_id') != PRIMARY or config.get('case', {}).get('case_id') != PRIMARY:
        raise ValueError('rear Native runner supports the exact uncontrolled rear-pass case')
    if config.get('rate_hz') != 20 or config.get('frames') != 160:
        raise ValueError('original 20 Hz eight-second capture required')
    if [item.get('name') for item in config.get('cameras', [])] != list(CAMERA_NAMES):
        raise ValueError('four named original source cameras required')
    if config.get('required_atoms') != []:
        raise ValueError('unreviewed source observation terms cannot be Core atoms')
    step = float(config.get('route_step_m', 2.0))
    speed = float(config.get('target_speed_mps', 5.0))
    overview_height_delta = float(config.get('overview_height_delta_m', 0.0))
    if not 1 <= step <= 3 or not 0 < speed <= 12 or not 0 <= overview_height_delta <= 2:
        raise ValueError('unsupported Native route or controller bounds')
    return step, speed, overview_height_delta


def device_inventory(world, world_map, pair):
    """Conservatively reject route-road signals and nearby Native lights."""
    roads = {pair['subject']['approach_road_id'], pair['opposing']['approach_road_id']}
    xml = world_map.to_opendrive()
    root = ElementTree.fromstring(xml)
    road_signals = []
    for road in root.findall('road'):
        if int(road.get('id')) in roads:
            road_signals.extend({'road_id': int(road.get('id')), 'signal_id': signal.get('id')}
                                for signal in road.findall('./signals/signal'))
    junction = next(w for w in pair['subject']['path'] if w.is_junction)
    center = junction.transform.location
    nearby_lights = []
    for actor in world.get_actors():
        if str(actor.type_id).startswith('traffic.traffic_light') and actor.get_location().distance(center) <= 35:
            nearby_lights.append({'native_id': actor.id, 'type_id': actor.type_id})
    if road_signals or nearby_lights:
        raise ValueError('uncontrolled exact case has possible governing official device')
    return {'governing_device': 'none', 'candidate_road_signals': road_signals,
            'candidate_nearby_lights': nearby_lights,
            'inspection_scope': 'both original approach roads and 35 m around the selected junction',
            'legal_device_applicability': 'unreviewed'}


def _turn_progress(actor, initial_heading):
    yaw = math.radians(float(actor.get_transform().rotation.yaw))
    current = (math.cos(yaw), math.sin(yaw))
    cross = initial_heading[0]*current[1] - initial_heading[1]*current[0]
    dot = initial_heading[0]*current[0] + initial_heading[1]*current[1]
    return math.degrees(math.atan2(cross, dot)) > 3


def run(output, host='127.0.0.1', port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from opposing_turn_camera_capture import CAMERAS, FFmpegSourceSink, TurnCameraCapture

    output = Path(output)
    config = json.loads((output / 'config.json').read_text())
    step, speed, overview_height_delta = check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original_settings = world.get_settings()
    actors, sinks = [], {}
    cameras = pipeline = frame_map = recorder = None
    frames = []
    failed = False
    restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        world_map = world.get_map()
        pair = choose_native_pair(world_map, step_m=step)
        devices = device_inventory(world, world_map, pair)
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        for route in (pair['subject'], pair['opposing']):
            actor = world.try_spawn_actor(blueprint, route['path'][0].transform)
            if actor is None:
                raise ValueError('opposing-left-turn Native vehicle spawn failed')
            actors.append(actor)
        topology = {
            'source_map': {'name': world_map.name,
                           'opendrive_sha256': hashlib.sha256(world_map.to_opendrive().encode()).hexdigest()},
            'junction_id': pair['junction_id'],
            'approach_road_id': pair['subject']['approach_road_id'],
            'approach_lane_ids': [pair['subject']['approach_lane_id'], pair['opposing']['approach_lane_id']],
            'exit_road_ids': [pair['subject']['exit_road_id'], pair['opposing']['exit_road_id']],
            'both_highways_two_directional': True, 'same_intersection': True,
            'opposing_approaches': True,
            'selection_basis': pair['selection_basis'],
            'legal_highway_classification': 'unreviewed',
        }
        recorder = OpposingTurnRecorder(output, topology, devices)
        for name in CAMERAS:
            sinks[name] = FFmpegSourceSink(output, name)
        cameras = TurnCameraCapture(world, carla, actors[0], sinks,
                                    overview_height_delta_m=overview_height_delta)
        pipeline = PipelineCapture(client, actors[0], output, PRIMARY,
                                   required_observations=config['required_atoms'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        indices = [0, 0]
        start_time = None
        routes = [pair['subject'], pair['opposing']]
        for tick in range(config['frames']):
            indices, commands = command_pair(actors, [route['path'] for route in routes],
                                              indices, tick, start_delays=(2, 0),
                                              target_speeds=(speed * 0.85, speed))
            for actor, command in zip(actors, commands):
                actor.apply_control(carla.VehicleControl(**command))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('original opposing-turn snapshot/frame mismatch')
            if start_time is None:
                start_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start_time
            cameras.wait_for_frame(frame)
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('original opposing-turn trace/frame join differs')
            frame_map.append(frame, time_s)
            on_junction = []
            turning = []
            for actor, route in zip(actors, routes):
                waypoint = world_map.get_waypoint(actor.get_location())
                on_junction.append(bool(waypoint and waypoint.is_junction and
                                         waypoint.get_junction().id == pair['junction_id']))
                turning.append(_turn_progress(actor, route['approach_heading_xy']))
            recorder.append(frame, time_s, actors[0], actors[1],
                            subject_in_intersection=on_junction[0],
                            opposing_in_intersection=on_junction[1],
                            subject_turning_left=turning[0], opposing_turning_left=turning[1])
            frames.append(frame)
        cameras.verify_frames(frames)
    except BaseException:
        failed = True
        raise
    finally:
        if recorder:
            recorder.close()
        if frame_map:
            frame_map.close()
        if pipeline:
            pipeline.close(confirmed=not failed)
        if cameras:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original_settings)
        current = world.get_settings()
        restored = (current.synchronous_mode == original_settings.synchronous_mode and
                    current.fixed_delta_seconds == original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('original opposing-turn world settings restoration differs')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)}) + '\n')
    seal_capture(output, frames=len(frames), restoration={'restored': restored}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERA_NAMES},
                 context={'native_map_name': world.get_map().name,
                          'junction_id': pair['junction_id']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads(Path(args.config).read_text()))
    elif args.output_dir:
        run(args.output_dir, args.host, args.port)
    else:
        parser.error('--output-dir required without --check')


if __name__ == '__main__':
    main()
