"""Proposed Native moving-follow capture. Only --check has run on CPU.

Execution requires an exclusively owned CARLA endpoint supplied by the operator.
The runner never starts a server, accesses campaign state, or accepts a recording.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from engineering import CANDIDATES, ego_velocity_request, parameters
from geometry import (DURATION_S, GAP_TARGET_M, LANE_ID, LANE_Y_M,
                      RATE_HZ, ROAD_ID, check as geometry_check, open_drive)

HERE = Path(__file__).resolve().parent


def cameras(candidate):
    wide = candidate == 'fallback3'
    return [
        {'name': 'overview', 'width': 1920, 'height': 1080,
         'fov_deg': 110 if wide else 90, 'xyz_m': [-9, 0, 2.0 if wide else 1.65]},
        {'name': 'approach', 'width': 1280, 'height': 720,
         'fov_deg': 110 if wide else 90, 'xyz_m': [-1, 0, 2.0 if wide else 1.65]},
        {'name': 'reference_corner', 'width': 1280, 'height': 720,
         'fov_deg': 110 if wide else 90, 'xyz_m': [1.3, -0.7, 2.0 if wide else 1.65]},
        {'name': 'driver_reference', 'width': 1280, 'height': 720,
         'fov_deg': 110 if wide else 90, 'xyz_m': [0.2, 0.2, 2.0 if wide else 1.65]}]


def check(config):
    geometry = geometry_check()
    suffix, candidate = config['case_suffix'], config['candidate_id']
    if suffix not in GAP_TARGET_M or candidate not in CANDIDATES:
        raise ValueError('Unknown C102304 case/candidate')
    if config['case_id'].rsplit('__', 1)[-1] != suffix:
        raise ValueError('Case identity differs from following condition')
    if config['cell_id'] != 'C102304' or config['law_id'] != 'NRS-484B-127-1' or config['actor'] != 'motor_vehicle_driver':
        raise ValueError('Frozen assignment identity differs')
    if config['duration_s'] != DURATION_S or config['rate_hz'] != RATE_HZ:
        raise ValueError('Full following capture window changed')
    plan = parameters(suffix, candidate)
    profile = cameras(candidate)
    if [(c['width'], c['height']) for c in profile] != [(1920,1080),(1280,720),(1280,720),(1280,720)]:
        raise ValueError('Four-view capture profile changed')
    if [(c['name'],c['width'],c['height']) for c in config['cameras']] != [
            (c['name'],c['width'],c['height']) for c in profile]:
        raise ValueError('Declared and executed camera contracts differ')
    return {'authored_geometry': geometry, 'engineering': plan,
            'camera_names': [c['name'] for c in profile],
            'native_imported': False, 'physical_success_claimed': False}


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(points) != 4:
        raise RuntimeError('Native actor body has no four-vertex ground footprint')
    return [list(p) for p in points]


def actor_sample(actor, mapping):
    pose = actor.get_transform()
    waypoint = mapping.get_waypoint(pose.location, project_to_road=False)
    if waypoint is None:
        raise RuntimeError('Original Native actor has no lane waypoint')
    direction = pose.get_forward_vector()
    norm = math.hypot(direction.x, direction.y)
    if norm < .99:
        raise RuntimeError('Original Native actor heading invalid')
    velocity = actor.get_velocity()
    return {'native_road_id': waypoint.road_id,
            'native_lane_id': waypoint.lane_id,
            'native_forward_xy': [direction.x/norm, direction.y/norm],
            'native_body_xy_m': footprint(actor),
            'native_center_xy_m': [pose.location.x, pose.location.y],
            'speed_mps': math.hypot(velocity.x, velocity.y)}


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file():
        raise ValueError('Use a new materialized exact-case output directory')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    state = snapshot(client)
    if state['settings'].synchronous_mode or any(a.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
                                                   for a in prior.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous world ownership required')
    owned, encoders, encoder_logs, camera_queues, channels = [], {}, {}, {}, {}
    capture = None
    changed = False
    error = None
    restored = None
    frames = 0
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        native_xml = mapping.to_opendrive()
        native_hash = hashlib.sha256(native_xml.encode()).hexdigest()
        survey = {}
        for name, x in (('before_crest', -50), ('crest', 0), ('after_crest', 50)):
            waypoint = mapping.get_waypoint(carla.Location(x=x, y=LANE_Y_M, z=5), project_to_road=True,
                                             lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id != ROAD_ID or waypoint.lane_id != LANE_ID:
                raise RuntimeError('Native road/lane survey differs at '+name)
            survey[name] = {'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                            'native_z_m': waypoint.transform.location.z}
        if not survey['crest']['native_z_m'] > survey['before_crest']['native_z_m']+3:
            raise RuntimeError('Native hill crest was not realized')
        write_new(output/'road_geometry.json', {'native_map_sha256': native_hash,
                                                'authored_map_sha256': hashlib.sha256(open_drive().encode()).hexdigest(),
                                                'survey': survey,
                                                'public_highway_status_verified': False})
        plan = parameters(config['case_suffix'], config['candidate_id'])
        ego_x = plan['ego_start_x_m']
        lead_x = ego_x + 2.4 + 4.5 + plan['target_bumper_gap_m']
        library = world.get_blueprint_library()
        ego_bp = library.find('vehicle.lincoln.mkz_2020')
        lead_bp = library.find('vehicle.carlamotors.firetruck')
        ego = world.spawn_actor(ego_bp, carla.Transform(carla.Location(x=ego_x, y=LANE_Y_M, z=1)))
        owned.append(ego)
        lead = world.spawn_actor(lead_bp, carla.Transform(carla.Location(x=lead_x, y=LANE_Y_M, z=1)))
        owned.append(lead)
        initial = {'ego': footprint(ego), 'lead': footprint(lead)}
        if min(v[0] for v in initial['lead'])-max(v[0] for v in initial['ego']) <= 0:
            raise RuntimeError('Actual Native bodies lack initial bumper clearance')
        write_new(output/'native-construction-context.json', {'case_id': config['case_id'],
            'candidate_id': config['candidate_id'], 'native_map_sha256': native_hash,
            'ego_blueprint': ego.type_id, 'lead_blueprint': lead.type_id,
            'initial_native_bodies': initial, 'requested_plan': plan,
            'physical_success_claimed': False})
        for spec in cameras(config['candidate_id']):
            sensor_bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', spec['width']), ('image_size_y', spec['height']),
                               ('fov', spec['fov_deg']), ('sensor_tick', 0)):
                sensor_bp.set_attribute(key, str(value))
            x, y, z = spec['xyz_m']
            camera = world.spawn_actor(sensor_bp,
                carla.Transform(carla.Location(x=x, y=y, z=z)), attach_to=ego)
            owned.append(camera)
            camera_queues[spec['name']] = queue.Queue()
            camera.listen(camera_queues[spec['name']].put)
            encoder_logs[spec['name']] = (output/(spec['name']+'.encoder.log')).open('x')
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f"{spec['width']}x{spec['height']}",
                '-r',str(RATE_HZ),'-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(spec['name']+'.mkv'))], stdin=subprocess.PIPE,
                stderr=encoder_logs[spec['name']])
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        (output/'channels').mkdir()
        for item in config['recording_description']['channels']:
            channels[item['name']] = (output/'channels'/(item['name']+'.jsonl')).open('x')
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native_samples.jsonl').open('x') as samples, \
             (output/'video_frames.jsonl').open('x') as video_frames:
            for index in range(DURATION_S*RATE_HZ):
                before_ego, before_lead = footprint(ego), footprint(lead)
                before_gap = min(v[0] for v in before_lead)-max(v[0] for v in before_ego)
                ego_request = ego_velocity_request(plan, before_gap)
                ego.set_target_velocity(carla.Vector3D(x=ego_request))
                lead.set_target_velocity(carla.Vector3D(x=plan['lead_target_speed_mps']))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds-start
                observed = {'native_frame': frame, 'time_s': time_s,
                            'ego': actor_sample(ego, mapping), 'lead': actor_sample(lead, mapping),
                            'requested_velocity_mps': {'ego': ego_request,
                                                       'lead': plan['lead_target_speed_mps']}}
                samples.write(json.dumps(observed, allow_nan=False)+'\n')
                capture.capture(frame, time_s, extra={'c102304_native': observed})
                ego_sample, lead_sample = observed['ego'], observed['lead']
                bumper_gap = min(v[0] for v in lead_sample['native_body_xy_m'])-max(
                    v[0] for v in ego_sample['native_body_xy_m'])
                values = {
                    'kin.speed': {'ego_mps': ego_sample['speed_mps'], 'lead_mps': lead_sample['speed_mps']},
                    'st.lane': {'ego': [ego_sample['native_road_id'], ego_sample['native_lane_id']],
                                'lead': [lead_sample['native_road_id'], lead_sample['native_lane_id']]},
                    'rel.surface_gap': {'longitudinal_bumper_gap_m': bumper_gap,
                                        'source': 'original Native four-vertex bodies'},
                    'rel.ahead_behind_in_lane': {'ego_behind_lead': bumper_gap > 0,
                        'same_lane': ego_sample['native_road_id'] == lead_sample['native_road_id'] and
                                     ego_sample['native_lane_id'] == lead_sample['native_lane_id']},
                    'native_body_pose_control': observed,
                    'camera_frame_join': {'native_frame': frame, 'video_frame': index}}
                for name, stream in channels.items():
                    stream.write(json.dumps({'time_s': time_s, 'value': values[name]}, allow_nan=False)+'\n')
                for spec in cameras(config['candidate_id']):
                    image = camera_queues[spec['name']].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[spec['name']].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec['height'], spec['width'], 4)[:,:,:3][:,:,::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                video_frames.write(json.dumps({'video_frame': index, 'native_frame': frame,
                                                'carla_frame': frame, 'time_s': time_s})+'\n')
                frames += 1
        write_new(output/'following_context.json', {
            'source_kind': 'native_observation', 'native_map_sha256': native_hash,
            'observed_frame_count': frames, 'native_road_id': ROAD_ID, 'native_lane_id': LANE_ID,
            'hill_crest_profile': survey, 'traffic': 'only spawned actor inventory recorded; ambient traffic not inferred',
            'surface': 'Native OpenDRIVE proposal and clear weather; friction not independently measured',
            'visibility': 'original camera sources require independent pixel audit',
            'highway_public_availability': 'unverified; Native map geometry is not public designation proof',
            'apparatus_response_status': 'unverified; no emergency privilege inferred',
            'ego_emergency_business_status': 'ordinary-driver blueprint; legal status unverified'})
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
    finally:
        for stream in channels.values():
            stream.close()
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'owned_actor_cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, state)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        write_new(output/'native-capture-report.json', {'case_id': config['case_id'],
            'candidate_id': config['candidate_id'], 'frames': frames,
            'expected_frames': DURATION_S*RATE_HZ, 'restoration': restored,
            'error': error, 'accepted': False, 'required_saved_checks': [
                'original actor/body/lane measurements','full camera/Native frame join',
                'public highway and traffic context','independent pixel and saved processing audits']})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json: '+str(error))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = json.loads((HERE/'config.json').read_text())
    if args.check:
        print(json.dumps(check(config), allow_nan=False))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Explicit materialized output and owned Native endpoint required')
        execute(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
