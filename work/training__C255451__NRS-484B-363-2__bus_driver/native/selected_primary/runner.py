"""Survey-gated Native bus school-crossing-zone attempt for exact condition_b.

`--check` is CPU only. Physical capture requires local CARLA ownership and a
reviewed speed-zone survey; requested speed is never an observed velocity.
"""
import argparse
import hashlib
import json
import math
import queue
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C255451__NRS-484B-363-2__bus_driver'
CASE = AID + '__selected_d08892c9__condition_b'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600
MPS_PER_MPH = 0.44704


def config_check():
    config = json.loads((HERE/'config.json').read_text())
    if (config.get('case_id') != CASE or config.get('selected_case_id') != CASE or
            config.get('cell_id') != 'C255451' or config.get('law_id') != 'NRS-484B-363-2' or
            config.get('actor') != 'bus_driver' or config.get('candidate_id') != 'primary' or
            config.get('rate_hz') != 20 or config.get('duration_s') != 30 or
            config.get('frames') != COUNT or type(config.get('target_mph')) not in (int, float) or
            not math.isfinite(config['target_mph']) or not (0 < config['target_mph'] <= 30) or
            not config.get('planned_context') or
            [c.get('name') for c in config.get('cameras', [])] != list(CAMERAS) or
            [(c.get('width'), c.get('height')) for c in config['cameras']] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] or
            config.get('physical_acceptance_claimed') is not False or config.get('legal_verdict') is not None):
        raise ValueError('Exact bus school-crossing-zone case identity or capture contract differs')
    return {'case_id': CASE, 'frames': COUNT, 'cameras': list(CAMERAS),
            'carla_imported': False, 'physical_acceptance_claimed': False}


def survey_check(survey):
    keys = ('map_name', 'survey_source', 'zone_establishment_source', 'installed_sign_source',
            'calendar_source', 'school_hours_source', 'half_hour_window_source',
            'beacon_source', 'beacon_phase_source', 'beacon_lights_source',
            'nonbeacon_sign_schedule_source', 'children_source',
            'civil_time_source', 'motor_bus_class_source',
            'zone_boundary_source', 'governing_road_direction_source',
            'ego_blueprint', 'spawn_xyz_m', 'spawn_yaw_deg', 'camera_world_transforms',
            'child_blueprints', 'child_world_transforms',
            'road_axis_xy', 'zone_station_bounds_m', 'civil_start_iso', 'authorized_mph', 'road_id',
            'travel_direction_id', 'reviewed_plan_case_id', 'planned_context_source', 'planned_context',
            'installed_sign_geometry')
    for key in keys:
        if key not in survey or survey[key] is None or survey[key] == '':
            raise ValueError('Missing reviewed Native survey source: ' + key)
    if len(survey['spawn_xyz_m']) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in survey['spawn_xyz_m']):
        raise ValueError('Invalid surveyed spawn')
    axis = survey['road_axis_xy']
    if len(axis) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in axis) or abs(math.hypot(*axis)-1) > .01:
        raise ValueError('Surveyed road axis must be unit length')
    bounds = survey['zone_station_bounds_m']
    if len(bounds) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in bounds) or bounds[0] >= bounds[1]:
        raise ValueError('Invalid surveyed zone bounds')
    if survey['authorized_mph'] != 25:
        raise ValueError('School-crossing-zone clause requires 25 mph')
    config = json.loads((HERE/'config.json').read_text())
    if survey['reviewed_plan_case_id'] != CASE or survey['planned_context'] != config['planned_context']:
        raise ValueError('Survey does not bind exact planned school-crossing-zone condition')
    try:
        civil_start = datetime.fromisoformat(survey['civil_start_iso'])
        if civil_start.tzinfo is None or civil_start.utcoffset() is None:
            raise ValueError('timezone absent')
    except (ValueError, TypeError) as exc:
        raise ValueError('Reviewed civil start needs timezone') from exc
    if set(survey['camera_world_transforms']) != set(CAMERAS):
        raise ValueError('Four surveyed source cameras required')
    if set(survey['child_blueprints']) != {'child_left', 'child_right'} or set(survey['child_world_transforms']) != {'child_left', 'child_right'}:
        raise ValueError('Two surveyed child actors required')
    for item in survey['child_world_transforms'].values():
        if len(item.get('xyz_m', [])) != 3 or len(item.get('rotation_deg', [])) != 3:
            raise ValueError('Invalid surveyed child transform')
    for item in survey['camera_world_transforms'].values():
        if len(item.get('xyz_m', [])) != 3 or len(item.get('rotation_deg', [])) != 3:
            raise ValueError('Invalid surveyed camera transform')
    sign = survey['installed_sign_geometry']
    if (not isinstance(sign, dict) or type(sign.get('actor_id')) is not int or
            not sign.get('asset_id') or not sign.get('geometry_source') or
            sign.get('sign_kind') != 'school_crossing_zone_speed_limit_25_mph' or
            len(sign.get('xyz_m', [])) != 3 or
            not all(type(v) in (int, float) and math.isfinite(v) for v in sign['xyz_m'])):
        raise ValueError('Source-identify installed 25 mph school crossing sign geometry')
    for name in ('overview', 'approach'):
        camera = survey['camera_world_transforms'][name]
        dx = sign['xyz_m'][0] - camera['xyz_m'][0]
        dy = sign['xyz_m'][1] - camera['xyz_m'][1]
        distance = math.hypot(dx, dy)
        yaw = math.radians(camera['rotation_deg'][1])
        forward = (math.cos(yaw), math.sin(yaw))
        angle = math.degrees(math.acos(max(-1., min(1.,
            (dx*forward[0] + dy*forward[1]) / max(distance, 1e-9)))))
        if not (3 <= distance <= 150 and angle <= 35):
            raise ValueError('Installed sign outside surveyed camera source view: ' + name)
    if survey['planned_context'] not in ('nonbeacon_sign_active', 'nonbeacon_sign_inactive'):
        beacon = survey.get('beacon_geometry')
        if not isinstance(beacon, dict) or beacon.get('sign_actor_id') != sign['actor_id'] or not beacon.get('geometry_source') or not beacon.get('alternation_controller_source'):
            raise ValueError('Source-identify installed beacon mounted with crossing sign')
        lights = beacon.get('yellow_lights')
        if not isinstance(lights, list) or len(lights) < 2 or len({lamp.get('actor_id') for lamp in lights if isinstance(lamp, dict)}) != len(lights):
            raise ValueError('Beacon requires two or more distinct alternating yellow lights')
        for lamp in lights:
            if (not isinstance(lamp, dict) or type(lamp.get('actor_id')) is not int or
                    lamp.get('color') != 'yellow' or not lamp.get('asset_id') or
                    len(lamp.get('xyz_m', [])) != 3 or
                    not all(type(v) in (int, float) and math.isfinite(v) for v in lamp['xyz_m']) or
                    math.dist(lamp['xyz_m'], sign['xyz_m']) > 5):
                raise ValueError('Beacon lamp lacks source-identified yellow geometry')
    elif survey.get('beacon_geometry') is not None:
        raise ValueError('Nonbeacon exception plan cannot claim an installed beacon')
    return survey


def transform(carla, xyz, rotation):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))


def capture(survey, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    survey_check(survey)
    output.mkdir(parents=True, exist_ok=True)
    if (output/'video_frames.jsonl').exists() or (output/'native_motion.jsonl').exists():
        raise ValueError('Retain prior Native source attempt; use a new directory')
    survey_path = output/'native_survey.json'
    if survey_path.exists():
        raise ValueError('Retain prior Native survey; use a new directory')
    survey_path.write_text(json.dumps(survey, sort_keys=True, allow_nan=False)+'\n')
    survey_sha256 = hashlib.sha256(survey_path.read_bytes()).hexdigest()
    client = carla.Client(host, port)
    client.set_timeout(120)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Live CARLA map differs from reviewed survey')
    devices = [survey['installed_sign_geometry']]
    if survey.get('beacon_geometry'):
        devices.extend(survey['beacon_geometry']['yellow_lights'])
    for device in devices:
        actor = world.get_actors().find(device['actor_id'])
        if (actor is None or actor.type_id != device['asset_id'] or
                actor.get_location().distance(carla.Location(
                    x=device['xyz_m'][0], y=device['xyz_m'][1], z=device['xyz_m'][2])) > .5):
            raise ValueError('Live installed sign/beacon actor differs from source-identified survey')
    settings = world.get_settings()
    old_sync, old_step = settings.synchronous_mode, settings.fixed_delta_seconds
    actors, encoders = [], {}
    core_capture = None
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        blueprint = world.get_blueprint_library().find(survey['ego_blueprint'])
        ego = world.try_spawn_actor(blueprint, transform(carla, survey['spawn_xyz_m'], [0, survey['spawn_yaw_deg'], 0]))
        if ego is None:
            raise RuntimeError('Surveyed ego spawn failed')
        actors.append(ego)
        waypoint = world.get_map().get_waypoint(ego.get_location(), project_to_road=True,
                                               lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != survey['road_id']:
            raise ValueError('Live ego road differs from reviewed zone road')
        children = {}
        for name in ('child_left', 'child_right'):
            child_spec = survey['child_world_transforms'][name]
            child_blueprint = world.get_blueprint_library().find(survey['child_blueprints'][name])
            child = world.try_spawn_actor(child_blueprint,
                transform(carla, child_spec['xyz_m'], child_spec['rotation_deg']))
            if child is None:
                raise RuntimeError('Surveyed child spawn failed: '+name)
            actors.append(child)
            children[name] = child
        queues = {}
        for spec in json.loads((HERE/'config.json').read_text())['cameras']:
            camera = world.get_blueprint_library().find('sensor.camera.rgb')
            camera.set_attribute('image_size_x', str(spec['width']))
            camera.set_attribute('image_size_y', str(spec['height']))
            camera.set_attribute('fov', '80')
            loc = survey['camera_world_transforms'][spec['name']]
            sensor = world.spawn_actor(camera, transform(carla, loc['xyz_m'], loc['rotation_deg']))
            actors.append(sensor)
            q = queue.Queue()
            sensor.listen(q.put)
            queues[spec['name']] = q
            encoders[spec['name']] = subprocess.Popen(
                ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgra',
                 '-video_size', f"{spec['width']}x{spec['height']}", '-framerate', '20',
                 '-i', '-', '-frames:v', str(COUNT), '-c:v', 'ffv1',
                 str(output/(spec['name']+'.mkv'))], stdin=subprocess.PIPE)
        core_capture = PipelineCapture(client, ego, output, CASE, required_observations=[])
        target_mps = json.loads((HERE/'config.json').read_text())['target_mph']*MPS_PER_MPH
        first_elapsed = None
        with (output/'video_frames.jsonl').open('w') as frame_file, (output/'native_motion.jsonl').open('w') as motion_file, (output/'children_context.jsonl').open('w') as child_file:
            for i in range(COUNT):
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                error = target_mps-speed
                ego.apply_control(carla.VehicleControl(throttle=max(0.0, min(.8, .25+.2*error)),
                                                       brake=max(0.0, min(1.0, -.2*error)), steer=0.0))
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise RuntimeError('Native world frame mismatch')
                if first_elapsed is None:
                    first_elapsed = snapshot.timestamp.elapsed_seconds
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                observed_waypoint = world.get_map().get_waypoint(pose.location, project_to_road=True,
                                                                  lane_type=carla.LaneType.Driving)
                if observed_waypoint is None:
                    raise RuntimeError('Native ego has no measured driving road')
                if velocity.x*survey['road_axis_xy'][0]+velocity.y*survey['road_axis_xy'][1] < -.1:
                    raise RuntimeError('Native ego motion opposes surveyed sign direction')
                core_capture.capture(native_frame, i/20,
                                     extra={'school_zone_source': {'road_id': observed_waypoint.road_id,
                                                                   'travel_direction_id': survey['travel_direction_id'],
                                                                   'zone_survey_sha256': survey_sha256}})
                frame_file.write(json.dumps({'video_frame': i, 'carla_frame': native_frame,
                                             'native_frame': native_frame,
                                             'time_s': snapshot.timestamp.elapsed_seconds-first_elapsed})+'\n')
                motion_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                              'source_kind': 'original_native_velocity',
                                              'road_id': observed_waypoint.road_id, 'ego_actor_id': ego.id,
                                              'travel_direction_id': survey['travel_direction_id'],
                                              'ego_x_m': pose.location.x, 'ego_y_m': pose.location.y,
                                              'velocity_x_mps': velocity.x,
                                              'velocity_y_mps': velocity.y,
                                              'velocity_z_mps': velocity.z})+'\n')
                child_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'source_kind': 'original_native_velocity',
                                             'children': [{'id': name, 'actor_id': child.id,
                                                           'x_m': child.get_location().x,
                                                           'y_m': child.get_location().y}
                                                          for name, child in children.items()]})+'\n')
                for camera_name, q in queues.items():
                    image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera frame does not join Native frame')
                    encoders[camera_name].stdin.write(image.raw_data)
        for proc in encoders.values():
            proc.stdin.close()
            if proc.wait(timeout=120) != 0:
                raise RuntimeError('Source camera encoding failed')
        core_capture.close(confirmed=True)
        core_capture = None
        (output/'school_zone_context.template.json').write_text(
            json.dumps(context_template(survey, ego.id, survey_sha256), indent=2)+'\n')
        return {'case_id': CASE, 'source_frames': COUNT,
                'requested_target_mps': target_mps, 'physical_acceptance_claimed': False}
    finally:
        if core_capture is not None:
            core_capture.close(confirmed=False)
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception:
                pass
        for proc in encoders.values():
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_step
        world.apply_settings(settings)


def context_template(survey, ego_actor_id, survey_sha256):
    """Copy surveyed sources while withholding all independent review facts."""
    return {
        'assignment_id': AID, 'case_id': CASE, 'review_kind': 'original_source_review',
        'reviewer': None, 'native_survey_sha256': survey_sha256,
        'planned_context_source': survey['planned_context_source'],
        'planned_context': survey['planned_context'],
        'zone_station_bounds_m': survey['zone_station_bounds_m'],
        'road_axis_xy': survey['road_axis_xy'], 'road_id': survey['road_id'],
        'ego_actor_id': ego_actor_id, 'travel_direction_id': survey['travel_direction_id'],
        'authorized_mph': survey['authorized_mph'], 'civil_start_iso': survey['civil_start_iso'],
        'camera_sha256': {}, 'review_required': True,
        'zone_designation_source': survey['zone_establishment_source'],
        'zone_sign_source': survey['installed_sign_source'],
        'calendar_source': survey['calendar_source'],
        'school_hours_source': survey['school_hours_source'],
        'half_hour_window_source': survey['half_hour_window_source'],
        'beacon_source': survey['beacon_source'],
        'beacon_phase_source': survey['beacon_phase_source'],
        'beacon_lights_source': survey['beacon_lights_source'],
        'children_source': survey['children_source'],
        'nonbeacon_sign_schedule_source': survey['nonbeacon_sign_schedule_source'],
        'vehicle_class_source': survey['motor_bus_class_source'],
        'civil_time_source': survey['civil_time_source'],
        'road_axis_source': survey['governing_road_direction_source'],
        'condition_stability_source': None,
        'zone_designated': None, 'school_session_day': None,
        'half_hour_window_exception': None, 'beacon_operational': None,
        'pupils_in_class': None, 'beacon_flashing': None,
        'nonbeacon_sign_in_effect': None, 'ego_is_motor_bus': None,
        'beacon_sign_present': None, 'beacon_yellow_light_count': None,
        'beacon_alternating_yellow': None,
        'condition_stable_30s': None,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    checked = config_check()
    if args.check:
        print(json.dumps(checked, sort_keys=True))
    else:
        if args.survey is None or args.output_dir is None:
            parser.error('Supply reviewed --survey and --output-dir')
        print(json.dumps(capture(json.loads(args.survey.read_text()), args.output_dir, args.host, args.port)))
