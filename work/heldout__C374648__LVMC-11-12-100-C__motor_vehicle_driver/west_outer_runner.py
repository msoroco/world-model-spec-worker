"""Native westbound outer-lane center-turn capture; CARLA is imported only at run time.

This authoring requests a left turn from a marked candidate center lane. It
retains the original lane/heading evidence and leaves legal designation open.
"""

import argparse
import json
from math import hypot
from pathlib import Path

from center_turn_cameras import CAMERAS, CenterTurnCameraCapture, LosslessSourceSink
from center_turn_construction import control_step, route_targets, select_candidate
from turn_origin_capture import TurnOriginRecorder

PREFIX = 'heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver__'


def check_config(config):
    case = PREFIX + 'left_outer_west'
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-12-100-C', 'C374648', 'motor_vehicle_driver'):
        raise ValueError('Wrong C374648 Native case identity')
    if config.get('selected_case_id') != case or config.get('case', {}).get('case_id') != case:
        raise ValueError('Runner requires exact westbound selected center-turn case')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 80, 4):
        raise ValueError('Center-turn runner requires 80 original frames at 20 Hz')
    if [item.get('name') for item in config.get('cameras', [])] != list(CAMERAS):
        raise ValueError('Four named center-turn source cameras required')
    for item in config['cameras']:
        if ((item.get('width'), item.get('height'), item.get('fov_deg')) !=
                (*CAMERAS[item['name']][2], CAMERAS[item['name']][3])):
            raise ValueError('Center-turn source camera profile differs')
    if not isinstance(config['case'].get('recording_description'), dict):
        raise ValueError('Missing exact center-turn recording description')
    return case


def run(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output_dir)
    config = json.loads((output/'config.json').read_text())
    case = check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    initial_settings = world.get_settings()
    actors, sinks, frames = [], {}, []
    cameras = pipeline = recorder = frame_map = None
    complete = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        carla_map = world.get_map()
        selected = select_candidate(carla_map, direction='west', approach_steps=6)
        targets = route_targets(selected, origin='outer')
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        ego = world.try_spawn_actor(blueprint, selected['outer_approach'][0].transform)
        if ego is None:
            raise ValueError('Center-turn subject spawn failed')
        actors.append(ego)
        context_path = output/'case_context.json'
        if context_path.exists():
            raise ValueError('Retain prior center-turn intent context')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = CenterTurnCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, case,
                                   required_observations=config.get('required_atoms', []))
        recorder = TurnOriginRecorder(output, carla_map, selected)
        frame_map = FrameMap(output/'video_frames.jsonl')
        target_index = 1
        start_time = None
        for _ in range(config['frames']):
            transform = ego.get_transform()
            position = transform.location
            while (target_index < len(targets)-1 and
                   hypot(position.x-targets[target_index][0],
                         position.y-targets[target_index][1]) < 1.5):
                target_index += 1
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            command = control_step((position.x, position.y), (forward.x, forward.y),
                                   (velocity.x, velocity.y), targets[target_index],
                                   target_speed_mps=8.)
            ego.apply_control(carla.VehicleControl(**command))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native snapshot frame differs')
            if start_time is None:
                start_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-start_time
            cameras.wait_for_frame(frame)
            pipeline.capture(frame, time_s)
            recorder.append(ego, frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        context = {
            'format': 'worker-authored-turn-intent', 'case_id': case,
            'ego_actor_id': ego.id, 'target_exit_road_id': int(selected['exit'].road_id),
            'target_exit_lane_id': int(selected['exit'].lane_id),
            'target_start_frame': frames[0], 'requested_maneuver': 'left turn',
            'candidate_center_road_id': selected['center_road_id'],
            'candidate_center_lane_id': selected['center_lane_id'],
            'map_markings_observed': selected['candidate_markings_observed'],
            'designation_authority_verified': False,
            'physical_completion_verified': False,
            'legal_acceptance_claimed': False}
        context['case_context'] = {key: value for key, value in context.items()}
        context_path.write_text(json.dumps(context) + '\n')
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
        world.apply_settings(initial_settings)
        restored = (world.get_settings().synchronous_mode == initial_settings.synchronous_mode
                    and world.get_settings().fixed_delta_seconds == initial_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native world restoration differs')
    if not complete or len(frames) != config['frames']:
        raise ValueError('Center-turn source capture incomplete')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)}) + '\n')
    seal_capture(output, frames=len(frames), restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'candidate_center_road_id': selected['center_road_id'],
                          'candidate_center_lane_id': selected['center_lane_id'],
                          'designation_authority_verified': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads((Path(args.output_dir or '.')/'config.json').read_text()))
    else:
        if not args.output_dir:
            parser.error('--output-dir required for Native capture')
        run(args.output_dir, args.host, args.port)
