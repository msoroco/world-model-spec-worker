"""Source-gated Native capture for C126120 single and multiple-movement U-turns.

A local operator supplies a reviewed site packet and executes this through the
runtime capture lifecycle. The source packet is intentionally absent here: no
actual divided-highway location or authority status has been verified on CPU.
"""

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import shutil

from barrier_construction import spawn_barrier_opening
from camera_encoder import FFV1Writer
from uturn_route import SegmentedController, validate_plan
from native_capture import CAMERAS, OriginalTickRecorder, original_cameras

ASSIGNMENT = 'testing__C126120__NRS-484B-227-1__motor_vehicle_driver'
CASE = ASSIGNMENT + '__source_verified_single_movement_uturn'
MULTIPLE_CASE = ASSIGNMENT + '__source_verified_multiple_movement_uturn'
CASE_IDS = {CASE, MULTIPLE_CASE}


def _pose(carla, values):
    if (not isinstance(values, list) or len(values) != 6 or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in values)):
        raise ValueError('Finite six-value Native pose required')
    return carla.Transform(
        carla.Location(x=values[0], y=values[1], z=values[2]),
        carla.Rotation(yaw=values[3], pitch=values[4], roll=values[5]))


def load_plan(path):
    path = Path(path)
    plan = json.loads(path.read_text())
    if plan.get('assignment_id') != ASSIGNMENT or plan.get('selected_case_id') not in CASE_IDS:
        raise ValueError('Exact C126120 U-turn case identity required')
    if plan.get('source_review_status') not in ('authored_cpu_diagnostic',
                                                'reviewed_original_map_and_cameras'):
        raise ValueError('Reviewed original Native map or explicit CPU diagnostic required')
    if plan.get('rate_hz') != 20 or type(plan.get('frames')) is not int or plan['frames'] < 80:
        raise ValueError('20 Hz and complete planned frame count required')
    source_refs = plan.get('source_refs')
    if not isinstance(source_refs, list) or not source_refs:
        raise ValueError('Original site source hashes required')
    for ref in source_refs:
        source = (path.parent / ref['path']).resolve()
        if not source.is_file() or not source.is_relative_to(path.parent.resolve()):
            raise ValueError('Original site source missing or outside packet directory')
        if hashlib.sha256(source.read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('Original site source hash differs')
    context = plan['divider_context']
    if context.get('native_map_id') != plan.get('native_map_name'):
        raise ValueError('Reviewed Native map differs from divider context')
    if set(plan.get('camera_poses', {})) != set(CAMERAS):
        raise ValueError('Four original source camera poses required')
    for pose in plan['camera_poses'].values():
        if len(pose) != 6 or any(type(v) not in (int, float) or not math.isfinite(v) for v in pose):
            raise ValueError('Finite original camera pose required')
    if len(plan.get('barrier_sections', [])) != 2:
        raise ValueError('Two physical barrier section plans required')
    for section in plan['barrier_sections']:
        if not section.get('blueprint_id'):
            raise ValueError('Native barrier blueprint required')
        if len(section.get('pose', [])) != 6:
            raise ValueError('Native barrier pose required')
    for key in ('ego_spawn_pose', 'other_spawn_pose'):
        if len(plan.get(key, [])) != 6:
            raise ValueError('Native participant pose required: ' + key)
    authority = plan.get('authority_source_ref')
    if not isinstance(authority, dict) or authority not in source_refs:
        raise ValueError('Separate source-hashed public-authority review required')
    validate_plan(context, plan['ego_segments'],
                  plan['planned_barrier_footprints_xy_m'],
                  body_radius_m=plan['ego_body_radius_m'])
    if len(plan.get('other_route_xy_m', [])) < 2:
        raise ValueError('Other vehicle route required')
    return plan


def validate_config(config, plan):
    if (config.get('assignment_id'), config.get('law_id'),
            config.get('cell_id'), config.get('actor')) != (
            ASSIGNMENT, 'NRS-484B-227-1', 'C126120', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact C80909 configuration identity')
    if set(config.get('supported_case_ids', [])) != CASE_IDS or config.get('selected_case_id') != plan['selected_case_id']:
        raise ValueError('Selected C126120 case/configuration differs')
    if config.get('rate_hz') != 20 or config.get('duration_s') != plan['frames'] / 20:
        raise ValueError('C126120 capture duration/rate differs')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError('Four original cameras required in configuration')
    if [(camera.get('name'), camera.get('width'), camera.get('height')) for camera in cameras] != [
            (name, *shape) for name, shape in CAMERAS.items()]:
        raise ValueError('Four original camera profile differs')
    if config.get('required_atoms') != [] or config.get('source_packets') != []:
        raise ValueError('Unsupported Core atom or source packet claim')
    physical = config.get('physical_completion', {})
    if (physical.get('criterion') != 'turn' or
            physical.get('motion_source') != 'movement_history.jsonl' or
            physical.get('body_key') != 'ego_body_vertices_xy_m' or
            physical.get('turn_degrees') != 180 or
            physical.get('engineering_tolerances_not_legal') is not True):
        raise ValueError('Source-bound U-turn physical completion descriptor required')
    return config


def _spawn_vehicle(world, blueprint, pose):
    actor = world.try_spawn_actor(blueprint, pose)
    if actor is None:
        raise ValueError('Original Native vehicle spawn failed')
    return actor


def copy_site_sources(plan, source_root, output):
    """Retain the exact source bytes referenced by the original site receipt."""
    source_root, output = Path(source_root).resolve(), Path(output).resolve()
    for ref in plan['source_refs']:
        source = (source_root / ref['path']).resolve()
        target = (output / ref['path']).resolve()
        if (not source.is_relative_to(source_root) or not target.is_relative_to(output) or
                not source.is_file() or target.exists() or
                hashlib.sha256(source.read_bytes()).hexdigest() != ref['sha256']):
            raise ValueError('Fresh original site source copy failed validation')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def run(world, client, carla, plan, output, source_root):
    """Capture a reviewed opening route and original four-camera frame joins."""
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    output = Path(output)
    capture_names = {'capture', 'road.xodr', 'trace.jsonl', 'carla_recorder.log',
                     'divider_context.json', 'site_source_receipt.json', 'barrier_receipt.json',
                     'movement_history.jsonl', 'video_frames.jsonl', 'control_history.jsonl'}
    capture_names.update(name + '.mkv' for name in CAMERAS)
    if not output.is_dir() or any((output / name).exists() for name in capture_names):
        raise ValueError('Fresh runtime capture source paths required')
    copy_site_sources(plan, source_root, output)
    if world.get_map().name != plan['native_map_name']:
        raise ValueError('Native world map differs from reviewed site')
    library = world.get_blueprint_library()
    vehicle_blueprint = library.find(plan['vehicle_blueprint_id'])
    if vehicle_blueprint is None:
        raise ValueError('Native vehicle blueprint missing')
    ego_pose = _pose(carla, plan['ego_spawn_pose'])
    other_pose = _pose(carla, plan['other_spawn_pose'])
    map_source = world.get_map()
    for role, pose in (('ego', ego_pose), ('other', other_pose)):
        waypoint = map_source.get_waypoint(pose.location, project_to_road=False)
        expected = plan['native_spawn_lanes'][role]
        if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (expected['road_id'], expected['lane_id']):
            raise ValueError('Native ' + role + ' road/lane differs from reviewed site')
    ego = _spawn_vehicle(world, vehicle_blueprint, ego_pose)
    other = None
    try:
        other = _spawn_vehicle(world, vehicle_blueprint, other_pose)
        sections = []
        for section in plan['barrier_sections']:
            blueprint = library.find(section['blueprint_id'])
            if blueprint is None:
                raise ValueError('Native barrier blueprint missing')
            sections.append((blueprint, _pose(carla, section['pose'])))
        context = plan['divider_context']
        with spawn_barrier_opening(world, sections, context['opening_xy_m'],
                                   plan['barrier_axis_xy']) as barrier:
            validate_plan(context, plan['ego_segments'],
                          barrier['barrier_footprints_xy_m'],
                          body_radius_m=plan['ego_body_radius_m'])
            context = dict(context)
            context['barrier_actors_source'] = 'Native barrier actor world vertices in barrier_receipt.json'
            (output / 'divider_context.json').write_text(json.dumps(context, indent=2) + '\n')
            (output / 'site_source_receipt.json').write_text(json.dumps({
                'native_map_name': plan['native_map_name'],
                'case_id': plan['selected_case_id'],
                'source_refs': plan['source_refs'],
                'authority_source_ref': plan.get('authority_source_ref'),
                'physical_acceptance_claimed': False}, indent=2) + '\n')
            receipt = {key: value for key, value in barrier.items() if key != 'actors'}
            (output / 'barrier_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            poses = {name: _pose(carla, values) for name, values in plan['camera_poses'].items()}
            ego_control = SegmentedController(plan['ego_segments'])
            other_control = SegmentedController([{'gear':'forward','waypoints_xy_m':plan['other_route_xy_m']}])
            with original_cameras(world, ego, poses) as read, ExitStack() as stack:
                writers = {}
                for name, (width, height) in CAMERAS.items():
                    writers[name] = stack.enter_context(FFV1Writer(output / (name + '.mkv'), width, height))
                history = stack.enter_context((output / 'movement_history.jsonl').open('x'))
                frames = stack.enter_context(FrameMap(output / 'video_frames.jsonl'))
                controls = stack.enter_context((output / 'control_history.jsonl').open('x'))
                recorder = OriginalTickRecorder(context, history, frames,
                    {name: writer.write for name, writer in writers.items()})
                pipeline = PipelineCapture(client, ego, output, plan['selected_case_id'],
                                           required_observations=[])
                confirmed = False
                try:
                    for _ in range(plan['frames']):
                        commands = {'ego': ego_control.step(ego), 'other': other_control.step(other)}
                        tick_frame = world.tick()
                        snapshot = world.get_snapshot()
                        if snapshot.frame != tick_frame:
                            raise ValueError('Original Native tick/snapshot identity differs')
                        waypoint = map_source.get_waypoint(ego.get_location(), project_to_road=False)
                        recorder.record(snapshot, ego, other, read(snapshot.frame),
                                        road_id=None if waypoint is None else waypoint.road_id)
                        controls.write(json.dumps({'frame': snapshot.frame,
                                                   'time_s': snapshot.timestamp.elapsed_seconds,
                                                   'commands': commands}, allow_nan=False) + '\n')
                        pipeline.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                    if recorder.index != plan['frames']:
                        raise ValueError('Incomplete original Native capture')
                    confirmed = True
                finally:
                    pipeline.close(confirmed=confirmed)
                encoder_codes = {name: writer.close() for name, writer in writers.items()}
                return encoder_codes
    finally:
        if other is not None:
            other.destroy()
        ego.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site-plan', default='site-plan.json')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    plan = load_plan(args.site_plan)
    if Path(args.config).is_file():
        validate_config(json.loads(Path(args.config).read_text()), plan)
    if args.check:
        print(json.dumps({'assignment_id': ASSIGNMENT, 'case_id': plan['selected_case_id'],
                          'planned_frames': plan['frames'], 'camera_sources': list(CAMERAS),
                          'cpu_plan_checked': True, 'physical_acceptance_claimed': False}))
        return
    if not args.output_dir:
        raise ValueError('Fresh --output-dir required for Native capture')
    if (plan['source_review_status'] != 'reviewed_original_map_and_cameras' or
            plan.get('authority_review_status') != 'reviewed_original_public_authority_document'):
        raise ValueError('Reviewed original Native map, cameras and authority document required')
    import carla
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Exact construction must be materialized before Native capture')
    saved = snapshot(client)
    failure = None
    encoder_codes = None
    try:
        world = client.get_world()
        current = world.get_settings()
        current.synchronous_mode = True
        current.fixed_delta_seconds = .05
        world.apply_settings(current)
        encoder_codes = run(world, client, carla, plan, output,
                            Path(args.site_plan).resolve().parent)
    except Exception as error:
        failure = error
    try:
        restored = restore(client, saved)
    except Exception as error:
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': plan['selected_case_id'], 'capture_sealed': False,
            'errors': [*([str(failure)] if failure else []),
                       'World restoration failed: ' + str(error)]}) + '\n')
        raise
    if failure is not None:
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': plan['selected_case_id'], 'capture_sealed': False,
            'errors': [str(failure)]}) + '\n')
        raise failure
    seal_capture(output, frames=plan['frames'], restoration=restored, errors=[],
                 encoder_exit_codes=encoder_codes,
                 context={'selected_case_id': plan['selected_case_id'],
                          'physical_site_and_authority_review_pending': True})


if __name__ == '__main__':
    main()
