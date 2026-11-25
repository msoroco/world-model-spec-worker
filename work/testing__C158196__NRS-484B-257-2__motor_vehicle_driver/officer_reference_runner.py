"""Native capture for exact C158196 officer and reference alternatives.

The --check path validates sourced construction without importing CARLA.
"""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path

from four_camera import CAMERAS, CAMERA_SIZES
from officer_camera_media import CameraMedia
from officer_capture_sequence import run as capture_sequence, write_receipt
from officer_direction import REFERENCE_SUFFIXES, PREFIX, behavior_suffix, native_bone_adapter
from officer_performer import spawn as spawn_officer
from officer_reference_plan import validate as validate_plan
from site_source import inventory
from stopping_reference import from_authored_site


ROOT = Path(__file__).resolve().parent


def validate_config(case_id):
    plan_review = validate_plan(ROOT)
    if case_id not in plan_review['case_ids']:
        raise ValueError('Unselected exact officer/reference case')
    plan = json.loads((ROOT / 'officer-reference-plan.json').read_text())
    row = next(item for item in plan['cases'] if item['case_id'] == case_id)
    camera_config = json.loads((ROOT / 'config.json').read_text())
    if ([item.get('name') for item in camera_config.get('cameras', [])] != list(CAMERAS) or
            any((item.get('width'), item.get('height')) != CAMERA_SIZES[item['name']]
                for item in camera_config['cameras']) or
            set(camera_config.get('camera_mounts', {})) != set(CAMERAS)):
        raise ValueError('Four exact original camera profiles required')
    site_path = ROOT / row['site_path']
    reference = from_authored_site(site_path)
    site = inventory(site_path)
    return {'plan': plan, 'row': row, 'camera_config': camera_config,
            'site_path': site_path, 'reference': reference, 'site': site}


def _transform(carla, location, rotation):
    return carla.Transform(carla.Location(**location), carla.Rotation(**rotation))


def _spawn_vehicle(world, library, blueprint_name, position, yaw, role, carla):
    blueprint = library.find(blueprint_name)
    blueprint.set_attribute('role_name', 'c158196_257_2_' + role)
    transform = _transform(carla,
                           {'x': position[0], 'y': position[1], 'z': 0.3},
                           {'yaw': yaw, 'pitch': 0.0, 'roll': 0.0})
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError('Native vehicle spawn failed: ' + role)
    return actor


def _camera_construction(world, config, carla):
    blueprints = {}
    mounts = {}
    library = world.get_blueprint_library()
    for item in config['cameras']:
        blueprint = library.find('sensor.camera.rgb')
        blueprint.set_attribute('image_size_x', str(item['width']))
        blueprint.set_attribute('image_size_y', str(item['height']))
        blueprint.set_attribute('fov', str(item['fov_deg']))
        blueprints[item['name']] = blueprint
    for name in CAMERAS:
        mount = config['camera_mounts'][name]
        mounts[name] = {'transform': _transform(carla, **mount['pose']),
                        'attach_to': mount['attach_to']}
    return blueprints, mounts


def _capture_world(world, client, output, selected, carla):
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    row, plan, site = selected['row'], selected['plan'], selected['site']
    if world.get_map().name not in {site['native_map_id'], 'OpenDriveMap'}:
        raise ValueError('Native officer/reference map differs from authored site')
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)
    library = world.get_blueprint_library()
    blueprints, mounts = _camera_construction(world, selected['camera_config'], carla)
    suffix = behavior_suffix(row['case_id'])
    with ExitStack() as stack:
        actors = {}
        for role, position, yaw in (('ego', row['ego_start_xy_m'], 0.0),
                                    ('other', row['other_start_xy_m'], 90.0)):
            actor = _spawn_vehicle(world, library, plan['actor_blueprints'][role],
                                   position, yaw, role, carla)
            stack.callback(actor.destroy)
            actors[role] = actor
        for role, expected in (('ego', (158190, -1)), ('other', (158194, -1))):
            waypoint = world.get_map().get_waypoint(actors[role].get_location(),
                                                    project_to_road=False)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != expected:
                raise ValueError('Native vehicle starts outside selected entrance: ' + role)
        officer = None
        adapter = None
        if suffix not in REFERENCE_SUFFIXES:
            x, y, z = row['officer_position_xyz_m']
            officer_blueprint = library.find(plan['actor_blueprints']['officer'])
            officer_blueprint.set_attribute('role_name', 'c158196_257_2_officer_performer')
            transform = _transform(carla, {'x': x, 'y': y, 'z': z},
                                   {'yaw': -90.0, 'pitch': 0.0, 'roll': 0.0})
            officer = stack.enter_context(spawn_officer(
                world, officer_blueprint, transform,
                carla.Location(x=0.0, y=0.0, z=0.0)))
            adapter = native_bone_adapter(carla, plan['officer_pose']['stop'],
                                          plan['officer_pose']['go'])
        actors['officer'] = officer
        intake = {'format': 'worker-subsection-2-officer-source-intake',
                  'site_id': site['native_map_id'],
                  'site_sha256': row['site_sha256'],
                  'officer_source': 'native-walker-actor-' + str(officer.id)
                  if officer is not None else None}
        with CameraMedia(world, output, blueprints, mounts, actors) as media:
            graph = PipelineCapture(client, actors['ego'], output, row['case_id'],
                                    required_observations=[])
            confirmed = False
            try:
                result = capture_sequence(
                    carla, world, actors['ego'], actors['other'], officer, adapter,
                    row['case_id'], selected['reference'], media.readback, intake,
                    go_frame=row['officer_go_frame'],
                    before_tick=lambda index: actors['other'].apply_control(
                        carla.VehicleControl(
                            throttle=0.0 if index < row['other_release_frame'] else 0.2,
                            brake=1.0 if index < row['other_release_frame'] else 0.0)),
                    after_tick=lambda source: graph.capture(source['carla_frame'],
                                                             source['time_s']))
                if media.encoder.count != 600:
                    raise ValueError('Four original camera streams incomplete')
                write_receipt(result, output / 'officer-reference-capture.json')
                with (output / 'officer_reference_history.jsonl').open('x') as history:
                    for source in result['rows']:
                        history.write(json.dumps({
                            'frame': source['carla_frame'],
                            'time_s': source['time_s'],
                            'ego_body_vertices_xy_m': source['ego_body_vertices_xy_m'],
                            'ego_speed_mps': source['ego_speed_mps'],
                        }, allow_nan=False) + '\n')
                with FrameMap(output / 'video_frames.jsonl') as frame_map:
                    for source in result['rows']:
                        frame_map.append(source['carla_frame'], source['time_s'],
                                         camera_frames={name: source['carla_frame']
                                                        for name in CAMERAS})
                confirmed = True
            finally:
                graph.close(confirmed=confirmed)
        return dict(media.encoder.exit_codes)


def capture(case_id, output_dir, host, port):
    import carla
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    selected = validate_config(case_id)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Materialized exact construction required')
    if output.is_relative_to(ROOT.parents[1] / 'runtime'):
        raise ValueError('Native output must not be written under runtime')
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved = snapshot(client)
    failure = None
    codes = None
    try:
        world = client.generate_opendrive_world(selected['site_path'].read_text())
        codes = _capture_world(world, client, output, selected, carla)
    except BaseException as error:
        failure = error
    try:
        restored = restore(client, saved)
    except BaseException as error:
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': case_id, 'capture_sealed': False,
            'errors': [*([str(failure)] if failure else []),
                       'World restoration failed: ' + str(error)]}) + '\n')
        raise
    if failure is not None:
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': case_id, 'capture_sealed': False,
            'errors': [str(failure)]}) + '\n')
        raise failure
    seal_capture(output, frames=600, restoration=restored, errors=[],
                 encoder_exit_codes=codes,
                 context={'selected_case_id': case_id,
                          'officer_authority_review_pending': True,
                          'stopping_reference_review_pending': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    case_id = args.case or json.loads((ROOT / 'config.json').read_text()).get('selected_case_id')
    selected = validate_config(case_id)
    if args.check:
        print(json.dumps({'case_id': case_id, 'site': selected['row']['site_path'],
                          'reference_kind': selected['reference']['kind'],
                          'cpu_config_checked': True, 'simulation_started': False}))
        return
    if not args.output_dir:
        raise ValueError('Native capture requires --output-dir')
    capture(case_id, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
