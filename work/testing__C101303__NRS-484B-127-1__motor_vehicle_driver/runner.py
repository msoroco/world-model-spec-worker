"""Native CARLA runner for the hill-crest following / lane-change cases.

CARLA is imported lazily inside run(). `--check` performs only CPU validation
(config, case table, generated OpenDRIVE) and never contacts a server.
The attempt directory must already hold config.json, construction.json and this
file (runtime.py capture/materialize does that).
"""
import argparse
import json
import math
import subprocess
import sys
import xml.dom.minidom
from pathlib import Path

import scenario as S

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
WARMUP_TICKS = 20


def load_config(directory):
    config = json.loads((Path(directory) / 'config.json').read_text())
    case = config['selected_case_id']
    if case not in config['supported_case_ids']:
        raise ValueError('Selected case is not supported by this bundle')
    variant = case.rsplit('__', 1)[1]
    params = S.case_params(variant)
    for key, value in config.get('case_parameters', {}).items():
        if params.get(key) != value:
            raise ValueError('Config case_parameters differ from the frozen case table: ' + key)
    if config['rate_hz'] != S.RATE_HZ or abs(config['duration_s'] - params['duration_s']) > 1e-9:
        raise ValueError('Config rate/duration differ from the scenario contract')
    names = [c['name'] for c in config['cameras']]
    if names != list(CAMERAS):
        raise ValueError('Four-view camera configuration required')
    return config, variant, params


def check(directory):
    config, variant, params = load_config(directory)
    xml.dom.minidom.parseString(S.opendrive_xml())
    return {'check': 'passed', 'case': config['selected_case_id'], 'variant': variant,
            'changed_from_base': S.changed_from_base(variant), 'carla_imported': 'carla' in sys.modules}


class Encoder:
    def __init__(self, path, width, height):
        self.process = subprocess.Popen(
            ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgra',
             '-s', '%dx%d' % (width, height), '-r', str(S.RATE_HZ), '-i', '-', '-c:v', 'ffv1', '-level', '3',
             '-pix_fmt', 'bgra', str(path)], stdin=subprocess.PIPE)
        self.frames = 0

    def write(self, raw):
        self.process.stdin.write(raw)
        self.frames += 1

    def close(self):
        self.process.stdin.close()
        return self.process.wait()


def foot(carla, actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    lowest = sorted(vertices, key=lambda v: v.z)[:4]
    return [[v.x, v.y, v.z] for v in lowest]


def run(directory, host, port):
    import carla  # lazy: CPU tests and --check never reach this line
    import queue
    from pipeline_capture import PipelineCapture
    from worker_exchange import world_restore
    from worker_exchange.native_output import FrameMap, seal_capture, capture_context
    directory = Path(directory).resolve()
    config, variant, params = load_config(directory)
    errors, actors, sensors, encoders, restoration = [], [], {}, {}, {}
    client = carla.Client(host, port)
    client.set_timeout(60.0)
    saved = world_restore.snapshot(client)
    try:
        (directory / 'channels').mkdir(exist_ok=False)
        client.generate_opendrive_world(S.opendrive_xml(), carla.OpendriveGenerationParameters(
            vertex_distance=2.0, max_road_length=500.0, wall_height=0.0, additional_width=0.6, smooth_junctions=True,
            enable_mesh_visibility=True))
        world = client.get_world()
        mapping = world.get_map()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = S.DT
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters(cloudiness=20.0, precipitation=params['precipitation'],
                          precipitation_deposits=params['precipitation_deposits'], wetness=params['wetness'],
                          sun_altitude_angle=60.0))
        library = world.get_blueprint_library()

        def spawn(role, lane, s, speed):
            blueprint = library.find('vehicle.tesla.model3')
            blueprint.set_attribute('role_name', role)
            waypoint = mapping.get_waypoint_xodr(S.ROAD_ID, lane, s)
            transform = waypoint.transform
            transform.location.z += 0.4
            actor = world.spawn_actor(blueprint, transform)
            actors.append(actor)
            physics = actor.get_physics_control()
            for wheel in physics.wheels:
                wheel.tire_friction = params['tire_friction']
            actor.apply_physics_control(physics)
            return actor

        ego = spawn('ego', S.EGO_LANE, S.EGO_S0_M, params['ego_set_speed_mps'])
        length = 2 * ego.bounding_box.extent.x
        lead_s = S.EGO_S0_M + length + params['initial_gap_m']
        lead = spawn('lead', S.EGO_LANE, lead_s, params['lead_speed_mps'])
        queued = None
        if params['queued_vehicle']:
            queued = spawn('queued', S.EGO_LANE, lead_s + length + params['queued_vehicle']['extra_gap_m'], params['lead_speed_mps'])
        for _ in range(WARMUP_TICKS):
            world.tick()
        for actor, speed in [(ego, params['ego_set_speed_mps']), (lead, params['lead_speed_mps'])] + ([(queued, params['lead_speed_mps'])] if queued else []):
            forward = actor.get_transform().get_forward_vector()
            actor.set_target_velocity(carla.Vector3D(forward.x * speed, forward.y * speed, forward.z * speed))
        # Cameras: sensor_tick 0 in synchronous mode => one image per tick.
        poses = {'overview': lambda: _overview(carla, ego, lead), 'approach': lambda: _attached(carla, ego, -12.0, 0.0, 3.2, -10.0, 0.0),
                 'reference_corner': lambda: _attached(carla, ego, 0.0, 12.0, 3.0, -12.0, -90.0),
                 'driver_reference': lambda: _attached(carla, ego, 0.3, -0.3, 1.25, -3.0, 0.0)}
        queues = {}
        for camera in config['cameras']:
            blueprint = library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(camera['width']))
            blueprint.set_attribute('image_size_y', str(camera['height']))
            blueprint.set_attribute('fov', str(camera['fov_deg']))
            blueprint.set_attribute('sensor_tick', '0.0')
            sensor = world.spawn_actor(blueprint, poses[camera['name']]())
            actors.append(sensor)
            q = queue.Queue()
            sensor.listen(q.put)
            sensors[camera['name']] = sensor
            queues[camera['name']] = q
            encoders[camera['name']] = Encoder(directory / (camera['name'] + '.mkv'), camera['width'], camera['height'])
        pi_ego, pi_lead, pi_queue = S.SpeedPI(), S.SpeedPI(), S.SpeedPI()
        streams = {name: (directory / 'channels' / (name + '.jsonl')).open('x') for name in
                   ('ego_speed_mps', 'lead_speed_mps', 'bumper_gap_m', 'ego_lane_id')}
        samples = (directory / 'following_samples.jsonl').open('x', buffering=1)
        state = {'lc_start': None, 'lead_leave': None}
        with PipelineCapture(client, ego, directory, config['selected_case_id'],
                             required_observations=config['required_atoms']) as capture, FrameMap(directory / 'video_frames.jsonl') as frames:
            total = int(round(params['duration_s'] * S.RATE_HZ))
            for i in range(total):
                t = i * S.DT
                ego_tr, lead_tr = ego.get_transform(), lead.get_transform()
                ego_v, lead_v = _speed(ego), _speed(lead)
                ego_s, lead_s_now = ego_tr.location.x, lead_tr.location.x
                lead_in_lane = mapping.get_waypoint(lead_tr.location).lane_id == mapping.get_waypoint(ego_tr.location).lane_id and lead_s_now > ego_s
                gap = (lead_s_now - ego_s - length) if lead_in_lane else None
                if state['lc_start'] is None and ego_s >= S.LANE_CHANGE_TRIGGER_S_M:
                    state['lc_start'] = t
                ego_target_t = S.lateral_offset_m(t - state['lc_start']) if state['lc_start'] is not None else S.lateral_offset_m(0)
                event = params['lead_event']
                if event and event['kind'] == 'leave_lane' and state['lead_leave'] is None and lead_s_now >= event['trigger_s_m']:
                    state['lead_leave'] = t
                lead_target_t = S.lateral_offset_m(t - state['lead_leave']) if state['lead_leave'] is not None else S.lateral_offset_m(0)
                _drive(carla, ego, pi_ego, S.ego_target_speed(params, gap, lead_v), ego_target_t, t, state['lc_start'])
                _drive(carla, lead, pi_lead, S.lead_target_speed(params, t, lead_s_now), lead_target_t, t, state['lead_leave'])
                if queued:
                    _drive(carla, queued, pi_queue, params['lead_speed_mps'], S.lateral_offset_m(0), t, None)
                for name, sensor in sensors.items():
                    sensor.set_transform(poses[name]())
                frame = world.tick()
                images = {}
                for name, q in queues.items():
                    image = q.get(timeout=60)
                    while image.frame < frame:
                        image = q.get(timeout=60)
                    if image.frame != frame:
                        raise RuntimeError('Camera frame mismatch: ' + name)
                    images[name] = image
                for name, image in images.items():
                    encoders[name].write(bytes(image.raw_data))
                row = capture.capture(frame, t)
                frames.append(frame, t)
                ego_tr, lead_tr = ego.get_transform(), lead.get_transform()
                ego_wp, lead_wp = mapping.get_waypoint(ego_tr.location), mapping.get_waypoint(lead_tr.location)
                ego_v, lead_v = _speed(ego), _speed(lead)
                gap_now = (lead_tr.location.x - ego_tr.location.x - length) if (lead_wp.lane_id == ego_wp.lane_id and lead_tr.location.x > ego_tr.location.x) else None
                sample = {'frame': frame, 'time_s': t, 'ego_lane_id': ego_wp.lane_id, 'ego_road_id': ego_wp.road_id,
                          'ego_s_m': ego_wp.s, 'ego_body_vertices_m': foot(carla, ego), 'ego_speed_mps': ego_v,
                          'lead_lane_id': lead_wp.lane_id, 'lead_s_m': lead_wp.s, 'lead_body_vertices_m': foot(carla, lead),
                          'lead_speed_mps': lead_v, 'lead_in_ego_lane': gap_now is not None, 'bumper_gap_m': gap_now,
                          'queued_speed_mps': _speed(queued) if queued else None,
                          'queued_s_m': mapping.get_waypoint(queued.get_location()).s if queued else None,
                          'ego_pitch_deg': ego_tr.rotation.pitch, 'ego_elevation_m': ego_tr.location.z}
                samples.write(json.dumps(sample, allow_nan=False) + '\n')
                for name, value in (('ego_speed_mps', ego_v), ('lead_speed_mps', lead_v), ('bumper_gap_m', gap_now if gap_now is not None else -1.0), ('ego_lane_id', ego_wp.lane_id)):
                    streams[name].write(json.dumps({'time_s': t, 'value': value}) + '\n')
        samples.close()
        for stream in streams.values():
            stream.close()
        context = {'case_parameters': params, 'authored_world_setup': True, 'public_way_road_ids': [S.ROAD_ID],
                   'crest_s_m': S.CREST_S_M, 'crest_vertical_curve_m': S.CREST_VERTICAL_CURVE_M, 'grade': S.GRADE,
                   'lane_width_m': S.LANE_WIDTH_M, 'road_length_m': S.ROAD_LENGTH_M,
                   'surface': {'wetness': params['wetness'], 'precipitation': params['precipitation'], 'tire_friction': params['tire_friction'],
                               'ice_or_snow': False, 'authored': 'synthetic generated asphalt; friction is an engineering setting, not measured'},
                   'vehicle_length_m': length, 'lane_change_trigger_s_m': S.LANE_CHANGE_TRIGGER_S_M}
        (directory / 'surface_context.json').write_text(json.dumps(context, indent=2, allow_nan=False) + '\n')
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for sensor in sensors.values():
            try:
                sensor.stop()
            except Exception as error:
                errors.append('sensor stop: ' + repr(error))
        codes = {}
        for name, encoder in encoders.items():
            codes[name] = encoder.close()
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception as error:
                errors.append('destroy: ' + repr(error))
        try:
            restoration = world_restore.restore(client, saved)
        except Exception as error:
            errors.append('restore: ' + repr(error))
            restoration = {'restored': False, 'error': repr(error)}
        if errors:
            (directory / 'native-run-status.json').write_text(json.dumps({'errors': errors, 'restoration': restoration}, indent=2))
    seal_capture(directory, frames=int(round(params['duration_s'] * S.RATE_HZ)), restoration=restoration, errors=errors,
                 encoder_exit_codes=codes, context={'case_id': config['selected_case_id'], 'map': 'generated hill_crest_following'})


def _speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)


def _drive(carla, actor, pi, target_speed, target_t, t, started):
    transform = actor.get_transform()
    speed = _speed(actor)
    throttle, brake = pi.step(target_speed, speed)
    y_des = -target_t  # CARLA y = -OpenDRIVE t on this straight, heading-0 road
    ahead = S.lateral_offset_m((t - started) + S.DT) if started is not None else target_t
    slope = (-(ahead - target_t)) / S.DT
    yaw_des = math.atan2(slope, max(speed, 1.0))
    yaw = math.radians((transform.rotation.yaw + 180) % 360 - 180)
    steer = S.steer_command(y_des - transform.location.y, yaw_des - yaw, speed)
    actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))


def _overview(carla, ego, lead):
    a, b = ego.get_location(), lead.get_location()
    return carla.Transform(carla.Location(x=(a.x + b.x) / 2 - 25.0, y=(a.y + b.y) / 2 + 2.0, z=a.z + 45.0), carla.Rotation(pitch=-60.0, yaw=0.0))


def _attached(carla, ego, forward, right, up, pitch, yaw_offset):
    t = ego.get_transform()
    yaw = math.radians(t.rotation.yaw)
    x = t.location.x + forward * math.cos(yaw) - right * math.sin(yaw)
    y = t.location.y + forward * math.sin(yaw) + right * math.cos(yaw)
    return carla.Transform(carla.Location(x=x, y=y, z=t.location.z + up), carla.Rotation(pitch=pitch, yaw=t.rotation.yaw + yaw_offset))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', default='.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.output_dir)))
        return
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
