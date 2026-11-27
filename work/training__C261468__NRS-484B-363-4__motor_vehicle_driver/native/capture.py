"""Survey-gated Native capture for an exact school-zone overtake case.

This module is importable on CPU hosts. CARLA and runtime capture modules are
loaded only when execute() is called by a local operator.
"""

import argparse
import hashlib
import json
import math
import os
import queue
import subprocess
from pathlib import Path

from controller import PassController, request_velocities
from scene import ASSIGNMENT, CASE_PLAN, spawn_pass_pair, validate_survey

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(value, message):
    if not value:
        raise ValueError(message)


def check(config):
    require(config.get('assignment_id') == ASSIGNMENT and
            config.get('case_id', '').startswith(ASSIGNMENT + '__'),
            'Exact school-zone assignment required')
    cases = {row['case_id']: row for row in json.loads(CASE_PLAN.read_text())['cases']}
    require(config['case_id'] in cases and
            config.get('requested_context') == cases[config['case_id']]['requested_context'],
            'Selected context differs from exact planned case')
    require(config.get('law_id') == 'NRS-484B-363-4' and
            config.get('frozen_cell') == {'layout': 'school_zone', 'maneuver': 'overtake',
                                          'control': 'other_vehicle'},
            'Frozen law or cell changed')
    require(config.get('frames') == 600 and config.get('fps') == 20 and
            config.get('duration_s') == 30, 'Exact 600-frame capture required')
    cameras = config.get('cameras')
    require(isinstance(cameras, list) and tuple(x.get('name') for x in cameras) == VIEWS,
            'Four canonical source cameras required')
    for i, camera in enumerate(cameras):
        size = (1920, 1080) if i == 0 else (1280, 720)
        require((camera.get('width'), camera.get('height')) == size and
                camera.get('fps') == 20 and
                isinstance(camera.get('location_xyz_m'), list) and
                len(camera['location_xyz_m']) == 3 and
                isinstance(camera.get('rotation_pyr_deg'), list) and
                len(camera['rotation_pyr_deg']) == 3 and
                all(type(v) in (int, float) and math.isfinite(v) for v in
                    camera['location_xyz_m'] + camera['rotation_pyr_deg']),
                'Camera source pose or profile invalid')
    require(config.get('physical_completion') == {} and
            config.get('legal_verdict') is None,
            'Capture configuration cannot claim physical or legal completion')
    require(config.get('required_atoms') and
            all(isinstance(x, str) for x in config['required_atoms']),
            'Pinned required atom list missing')
    return {'case_id': config['case_id'], 'frames': 600, 'fps': 20,
            'views': list(VIEWS), 'carla_contacted': False}


def lamp_sample(world, survey, native_frame, video_frame):
    """Read live lamp actor states; never substitute the requested flash flag."""
    if not survey['planned_context']['beacon_operational']:
        return None
    lamps = survey['beacon']['yellow_lights']
    ids, lit = [], []
    for spec in lamps:
        actor = world.get_actors().find(spec['actor_id'])
        require(actor is not None and actor.type_id == spec['asset_id'],
                'Original beacon lamp actor changed')
        require(callable(getattr(actor, 'get_state', None)),
                'Beacon lamp has no observable Native state')
        state = actor.get_state()
        name = str(state).lower()
        require(name.endswith(('yellow', 'off', 'red', 'green')),
                'Beacon lamp state is not interpretable')
        ids.append(actor.id)
        lit.append(name.endswith('yellow'))
    return {'video_frame': video_frame, 'native_frame': native_frame,
            'source_kind': 'original_lamp_state', 'lamp_actor_ids': ids,
            'yellow_lit': lit}


def execute(config, output_dir, survey_path, host='127.0.0.1', port=2000):
    check(config)
    survey_path = survey_path or os.environ.get('SCENARIO_CONTEXT_SURVEY')
    require(survey_path, 'Original school-zone context survey required')
    survey_bytes = Path(survey_path).read_bytes()
    survey = json.loads(survey_bytes)
    require(validate_survey(survey) == config['case_id'],
            'Survey does not bind selected exact case')
    require(survey.get('route_direction_id'), 'Original route direction identity missing')
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture, write_result
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'context-survey.json').open('xb') as saved:
        saved.write(survey_bytes)
    survey_sha = hashlib.sha256(survey_bytes).hexdigest()
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors, encoders, codes = [], [], {}, {}
    images = queue.Queue()
    completed = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        ego, other = spawn_pass_pair(world, carla, survey)
        actors.extend((ego, other))
        controller = PassController(survey,
                                    pass_side=config['pass_side'],
                                    lane_width_m=config['pass_lane_width_m'],
                                    ego_speed_mps=config['ego_speed_mps'],
                                    other_speed_mps=config['other_speed_mps'])
        for camera in config['cameras']:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            xyz = camera['location_xyz_m']
            pyr = camera['rotation_pyr_deg']
            transform = carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                        carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2]))
            sensor = world.spawn_actor(bp, transform, attach_to=ego)
            require(sensor is not None, 'Source camera spawn failed')
            actors.append(sensor)
            sensors.append(sensor)
            path = output / (camera['name'] + '.mkv')
            encoders[camera['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra',
                '-s', f"{camera['width']}x{camera['height']}", '-r', '20', '-i', '-',
                '-frames:v', '600', '-c:v', 'ffv1', '-level', '1', str(path)],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            sensor.listen(lambda image, name=camera['name']: images.put((name, image)))
        lamp_file = ((output / 'beacon_lamps.jsonl').open('x', buffering=1)
                     if survey['planned_context']['beacon_operational'] else None)
        try:
            with PipelineCapture(client, ego, output, config['case_id'],
                                 required_observations=config['required_atoms']) as capture, \
                    FrameMap(output / 'video_frames.jsonl') as frame_map, \
                    (output / 'pass_trace.jsonl').open('x', buffering=1) as trace:
                for frame in range(600):
                    epose, opose = ego.get_transform(), other.get_transform()
                    command = controller.step(
                        [epose.location.x, epose.location.y, epose.location.z],
                        [opose.location.x, opose.location.y, opose.location.z])
                    request_velocities(ego, other, carla, command)
                    native_frame = world.tick()
                    seen = set()
                    while len(seen) < 4:
                        name, image = images.get(timeout=15)
                        if image.frame != native_frame or name in seen:
                            continue
                        encoders[name].stdin.write(image.raw_data)
                        seen.add(name)
                    epose, opose = ego.get_transform(), other.get_transform()
                    ax, ay = survey['road_axis_xy']
                    def station(pose):
                        return pose.location.x * ax + pose.location.y * ay
                    def lateral(pose):
                        return -pose.location.x * ay + pose.location.y * ax
                    capture.capture(native_frame, frame / 20,
                                    extra={'video_frame': frame, 'other_actor_id': other.id,
                                           'context_survey_sha256': survey_sha})
                    frame_map.append(native_frame, frame / 20,
                                     camera_native_frames={name: native_frame for name in VIEWS},
                                     native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                    trace.write(json.dumps({
                        'video_frame': frame, 'native_frame': native_frame,
                        'source_kind': 'original_native_pose',
                        'ego_actor_id': ego.id, 'other_actor_id': other.id,
                        'ego_route_direction_id': survey['route_direction_id'],
                        'other_route_direction_id': survey['route_direction_id'],
                        'ego_station_m': station(epose), 'other_station_m': station(opose),
                        'ego_lateral_m': lateral(epose), 'other_lateral_m': lateral(opose),
                        'requested_velocity': command,
                        'context_survey_sha256': survey_sha}) + '\n')
                    if lamp_file is not None:
                        lamp_file.write(json.dumps(lamp_sample(world, survey, native_frame, frame)) + '\n')
        finally:
            if lamp_file is not None:
                lamp_file.close()
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            codes[name] = process.wait(timeout=180)
            require(codes[name] == 0 and (output / (name + '.mkv')).is_file(),
                    'Source camera encode failed: ' + name + ' ' + error.decode()[-200:])
        completed = True
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restored = restore(client, original)
        if completed and len(codes) == 4:
            seal_capture(output, frames=600, restoration=restored, errors=[],
                         encoder_exit_codes=codes, context={'case_id': config['case_id']})
            write_result(output, {
                'case_id': config['case_id'], 'measured_values': {'captured_frames': 600},
                'target_checks': [], 'setup_confirmed': False, 'behavior_attempted': True,
                'maneuver_completed': False, 'termination_reason': 'Source review pending',
                'physical_failure_flags': ['pass_motion_unreviewed', 'beacon_pixels_unreviewed',
                                           'school_calendar_unreviewed'],
                'trace_reference': 'trace.jsonl',
                'video_references': [x + '.mkv' for x in VIEWS],
                'video_frame_map_reference': 'video_frames.jsonl',
                'recording_description': config['recording_description'],
                'recording_evidence': {}, 'realized_observables': {},
                'provenance_kind': 'native', 'diagnostic_fixture': False,
                'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
                'accepted': False})
            record_native_exit(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--context-survey')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir, 'Output directory required')
        execute(config, args.output_dir, args.context_survey, args.host, args.port)
