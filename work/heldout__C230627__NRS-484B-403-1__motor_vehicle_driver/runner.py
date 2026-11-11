"""CARLA-lazy original capture request for C230627 U-turn comparisons."""

import argparse
import json
from math import hypot
from pathlib import Path

from u_turn_camera_capture import CAMERAS, LaneCameraCapture, LosslessSourceSink
from u_turn_construction import (control_step, participant_placement,
                                 select_u_turn_scene, u_turn_targets)
from u_turn_originals import UTurnSourceRecorder


SUFFIXES = ('safety_clear', 'safety_conflict')
PREFIX = 'heldout__C230627__NRS-484B-403-1__motor_vehicle_driver__'


def check_config(config):
    case_id = config.get('selected_case_id')
    if (case_id not in (PREFIX+suffix for suffix in SUFFIXES) or
            config.get('case', {}).get('case_id') != case_id):
        raise ValueError('Unknown C230627 exact U-turn case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-403-1', 'C230627', 'motor_vehicle_driver'):
        raise ValueError('C230627 U-turn identity differs')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 160, 8):
        raise ValueError('C230627 capture needs 160 frames at 20 Hz')
    if not isinstance(config.get('case', {}).get('recording_description'), dict):
        raise ValueError('Missing exact recording description')
    cameras = config.get('cameras', [])
    if [camera.get('name') for camera in cameras] != list(CAMERAS):
        raise ValueError('Four named U-turn source cameras required')
    for camera in cameras:
        profile = CAMERAS[camera['name']]
        if (camera.get('width'), camera.get('height'), camera.get('fov_deg')) != (
                *profile[2], profile[3]):
            raise ValueError('U-turn source camera profile differs')
    engineering = config.get('engineering', {})
    permitted = {'waypoint_spacing_m', 'route_candidate_index', 'arc_extension_m',
                 'oncoming_distance_m', 'following_distance_m',
                 'target_speed_mps', 'heading_gain', 'speed_gain'}
    if set(engineering) - permitted:
        raise ValueError('Unknown U-turn engineering knob')
    if case_id.endswith('__safety_clear') and engineering.get('oncoming_distance_m', 24) != 24:
        raise ValueError('Clear comparison participant placement differs')
    if case_id.endswith('__safety_conflict') and engineering.get('oncoming_distance_m') != 12:
        raise ValueError('Conflict comparison participant placement differs')
    return case_id


def _spawn_at(world, carla, blueprint, waypoint, xy):
    native = waypoint.transform
    location = carla.Location(x=float(xy[0]), y=float(xy[1]),
                              z=float(native.location.z) + .4)
    transform = carla.Transform(location, native.rotation)
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError('C230627 Native participant spawn failed')
    return actor


def run(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output_dir)
    config = json.loads((output/'config.json').read_text())
    check_config(config)
    engineering = config.get('engineering', {})
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original_settings = world.get_settings()
    actors = []
    cameras = pipeline = recorder = frame_map = None
    sinks = {}
    frames = []
    complete = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        scene = select_u_turn_scene(world.get_map(),
                                    waypoint_spacing_m=engineering.get('waypoint_spacing_m', 2.),
                                    candidate_index=engineering.get('route_candidate_index', 0))
        route = u_turn_targets(scene, arc_extension_m=engineering.get('arc_extension_m', 6.))
        placement = participant_placement(
            scene, oncoming_distance_m=engineering.get('oncoming_distance_m', 24.),
            following_distance_m=engineering.get('following_distance_m', 18.))
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego = world.try_spawn_actor(blueprint, scene['approach'].transform)
        if ego is None:
            raise ValueError('C230627 Native ego spawn failed')
        actors.append(ego)
        participants = {}
        for role, waypoint in (('oncoming', scene['opposite']),
                               ('following', scene['approach'])):
            participants[role] = _spawn_at(world, carla, blueprint,
                                           waypoint, placement[role])
            actors.append(participants[role])
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = LaneCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        recorder = UTurnSourceRecorder(output, ego, participants, scene)
        frame_map = FrameMap(output/'video_frames.jsonl')
        target_index = 1
        start_time = None
        for _ in range(config['frames']):
            transform = ego.get_transform()
            position = transform.location
            while (target_index < len(route['targets_xy_m'])-1 and
                   hypot(position.x-route['targets_xy_m'][target_index][0],
                         position.y-route['targets_xy_m'][target_index][1]) < 1.5):
                target_index += 1
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            command = control_step(
                (position.x, position.y), (forward.x, forward.y),
                (velocity.x, velocity.y), route['targets_xy_m'][target_index],
                target_speed_mps=engineering.get('target_speed_mps', 5.),
                heading_gain=engineering.get('heading_gain', 1.4),
                speed_gain=engineering.get('speed_gain', .25))
            ego.apply_control(carla.VehicleControl(**command))
            for actor in participants.values():
                actor.apply_control(carla.VehicleControl(throttle=.22))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('C230627 Native snapshot frame differs')
            if start_time is None:
                start_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-start_time
            cameras.wait_for_frame(frame)
            pipeline.capture(frame, time_s)
            recorder.append(frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        complete = True
    finally:
        if frame_map is not None:
            frame_map.close()
        if recorder is not None:
            recorder.close()
        if pipeline is not None:
            pipeline.close(confirmed=complete)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original_settings)
        restored = (world.get_settings().synchronous_mode == original_settings.synchronous_mode and
                    world.get_settings().fixed_delta_seconds == original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('C230627 Native world restoration differs')
    if not complete or len(frames) != config['frames']:
        raise ValueError('C230627 Native capture incomplete')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)})+'\n')
    seal_capture(output, frames=len(frames), restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'road_id': scene['road_id'],
                          'approach_lane_id': scene['approach_lane_id'],
                          'opposite_lane_id': scene['opposite_lane_id']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads(Path('config.json').read_text()))
        return
    if not args.output_dir:
        parser.error('--output-dir required for Native capture')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
