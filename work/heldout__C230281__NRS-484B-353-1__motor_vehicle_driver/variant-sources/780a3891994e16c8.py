"""CARLA-lazy acquisition for the first C230281 meeting/stop construction.

The output retains actor motion, commanded bus lights and four camera streams.
Commands and a bus blueprint name are not proof of required equipment, pupil
service, visible red lamps, or a legal/physical outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from school_bus_camera import CAMERAS, LosslessSourceSink, SchoolBusCameraCapture
from school_bus_controller import apply, motion_readback, select_meeting_waypoints, spawn_meeting_scene, target

ASSIGNMENT = 'heldout__C230281__NRS-484B-353-1__motor_vehicle_driver'
CASE_ID = ASSIGNMENT + '__meeting_resume_after_red_ceases'
FRAMES = 160


def check_plan(plan, case_id):
    if (plan.get('assignment_id'), plan.get('law_id'), plan.get('cell_id'), plan.get('actor')) != (
        ASSIGNMENT, 'NRS-484B-353-1', 'C230281', 'motor_vehicle_driver'):
        raise ValueError('School-bus frozen assignment identity differs')
    if case_id != CASE_ID or not any(c.get('case_id') == case_id and
                                      c.get('branch') == 'meeting_resume_after_red_ceases'
                                      for c in plan.get('cases', [])):
        raise ValueError('Unselected school-bus first case')
    return True


def check_scene(scene):
    if not isinstance(scene, dict) or not all(isinstance(scene.get(key), str) and scene[key]
                                             for key in ('bus_blueprint_id','subject_blueprint_id')):
        raise ValueError('School-bus scene blueprint IDs missing')
    service = scene.get('pupil_service')
    if (not isinstance(service, dict) or
        service.get('purpose') not in ('receiving', 'discharging') or
        not isinstance(service.get('walker_blueprint_id'), str) or
        not service['walker_blueprint_id'].startswith('walker.pedestrian.')):
        raise ValueError('School-bus pupil-service actor/purpose missing')
    if scene.get('auto_meeting_route') is True:
        if 'bus' in scene or 'subject' in scene:
            raise ValueError('School-bus scene mixes automatic and fixed poses')
        return scene
    for name in ('bus','subject'):
        pose = scene.get(name)
        if (not isinstance(pose, dict) or
            not isinstance(pose.get('location'), list) or len(pose['location']) != 3 or
            not isinstance(pose.get('rotation'), list) or len(pose['rotation']) != 3 or
            any(type(v) not in (int,float) or not math.isfinite(v)
                for v in pose['location'] + pose['rotation'])):
            raise ValueError('School-bus scene pose missing: ' + name)
    return scene


def _transform(carla, pose):
    return carla.Transform(carla.Location(*pose['location']),
                           carla.Rotation(*pose['rotation']))


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def spawn_pupil_service(world, carla, bus, service):
    """Place a walker beside the stopped bus and return its controlled travel axis."""
    transform = bus.get_transform()
    location = transform.location
    right = transform.get_right_vector()
    if not all(math.isfinite(value) for value in (
            location.x, location.y, location.z, right.x, right.y)):
        raise ValueError('School-bus pupil spawn geometry nonfinite')
    distance = 4.0 if service['purpose'] == 'receiving' else 1.8
    pupil_location = carla.Location(location.x + right.x * distance,
                                    location.y + right.y * distance,
                                    location.z + 0.3)
    pupil_transform = carla.Transform(pupil_location, transform.rotation)
    blueprint = world.get_blueprint_library().find(service['walker_blueprint_id'])
    pupil = world.try_spawn_actor(blueprint, pupil_transform)
    if pupil is None:
        raise ValueError('School-bus pupil actor spawn failed')
    direction = -1.0 if service['purpose'] == 'receiving' else 1.0
    return pupil, carla.Vector3D(right.x * direction, right.y * direction, 0.0)


def pupil_readback(pupil, bus, frame, time_s, purpose):
    point = pupil.get_location()
    bus_point = bus.get_location()
    velocity = pupil.get_velocity()
    values = (point.x, point.y, point.z, bus_point.x, bus_point.y, bus_point.z,
              velocity.x, velocity.y, velocity.z)
    if any(not math.isfinite(value) for value in values):
        raise ValueError('Original pupil-service readback nonfinite')
    return {'frame': frame, 'time_s': time_s, 'pupil_id': str(pupil.id),
            'bus_id': str(bus.id), 'requested_purpose': purpose,
            'pupil_xyz': [point.x, point.y, point.z],
            'bus_xyz': [bus_point.x, bus_point.y, bus_point.z],
            'pupil_speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            'pupil_distance_to_bus_m': math.sqrt(sum((a-b)**2 for a,b in zip(
                (point.x,point.y,point.z),(bus_point.x,bus_point.y,bus_point.z)))),
            'pupil_service_verified': False}


def close_all(actions):
    """Attempt every owner cleanup even if an earlier close fails."""
    errors = []
    for name, action in actions:
        try:
            action()
        except BaseException as error:
            errors.append((name, error))
    if errors:
        raise RuntimeError('School-bus Native cleanup failed: ' +
                           ', '.join(name for name, _ in errors)) from errors[0][1]


def run(plan, scene, output, *, host='127.0.0.1', port=2000):
    """Run one original acquisition; no synthetic or inferred visible signal."""
    check_plan(plan, CASE_ID)
    check_scene(scene)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name in ('motion_original.jsonl','pupil_original.jsonl','signal_command_original.jsonl',
                 'video_frames.jsonl','native-acquisition-inventory.json'):
        if (output / name).exists():
            raise ValueError('Retain prior school-bus Native source: ' + name)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original_settings = world.get_settings()
    actors = []
    camera = pipeline = frame_map = motion_file = signal_file = pupil_file = None
    sinks = {}
    captured = []
    completed = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        if scene.get('map_name') and world.get_map().name != scene['map_name']:
            raise ValueError('School-bus scene map identity differs')
        if scene.get('auto_meeting_route') is True:
            route = select_meeting_waypoints(world.get_map())
            bus_transform = route['bus_waypoint'].transform
            subject_transform = route['subject_waypoint'].transform
        else:
            bus_transform = _transform(carla, scene['bus'])
            subject_transform = _transform(carla, scene['subject'])
        construction = spawn_meeting_scene(world, carla, {
            'bus_blueprint_id': scene['bus_blueprint_id'],
            'subject_blueprint_id': scene['subject_blueprint_id'],
            'bus_transform': bus_transform,
            'subject_transform': subject_transform})
        bus, subject = construction['bus'], construction['subject']
        actors.extend((bus, subject))
        pupil, pupil_direction = spawn_pupil_service(world, carla, bus,
                                                     scene['pupil_service'])
        actors.append(pupil)
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        camera = SchoolBusCameraCapture(world, carla, subject, bus, sinks)
        pipeline = PipelineCapture(client, subject, output, CASE_ID,
                                   required_observations=[row['term'] for row in plan.get('observations',[])])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        motion_file = (output / 'motion_original.jsonl').open('x')
        pupil_file = (output / 'pupil_original.jsonl').open('x')
        signal_file = (output / 'signal_command_original.jsonl').open('x')
        start = None
        for index in range(FRAMES):
            operating = 20 <= index < 120
            phase = operating and index % 8 < 4
            light = carla.VehicleLightState.Special1 if phase else carla.VehicleLightState.NONE
            bus.set_light_state(light)
            prior = subject.get_velocity()
            speed = (prior.x**2 + prior.y**2 + prior.z**2)**.5
            command = target('meeting_resume_after_red_ceases', red_signal_operating=operating,
                             stop_observed=speed <= .05)
            apply(subject, carla.VehicleControl, command, speed_mps=speed)
            pupil.apply_control(carla.WalkerControl(
                direction=pupil_direction,
                speed=1.2 if 20 <= index < 100 else 0.0))
            frame = world.tick()
            camera.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native school-bus snapshot/frame differs')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Native school-bus trace/frame differs')
            row = motion_readback(subject,bus,
                                  [construction['subject_waypoint'].transform.get_forward_vector().x,
                                   construction['subject_waypoint'].transform.get_forward_vector().y],
                                  frame,time_s)
            bus_velocity = bus.get_velocity()
            row['bus_speed_mps'] = math.sqrt(bus_velocity.x**2 + bus_velocity.y**2 +
                                             bus_velocity.z**2)
            if not math.isfinite(row['bus_speed_mps']):
                raise ValueError('Native school-bus stop readback nonfinite')
            motion_file.write(json.dumps(row,allow_nan=False)+'\n')
            pupil_file.write(json.dumps(pupil_readback(
                pupil, bus, frame, time_s, scene['pupil_service']['purpose']),
                allow_nan=False)+'\n')
            signal_file.write(json.dumps({
                'frame':frame,'time_s':time_s,'bus_id':str(bus.id),
                'red_signal_commanded':operating,'red_phase_commanded':phase,
                'vehicle_light_state_readback':str(bus.get_light_state()),
                'front_red_visible':None,'rear_red_visible':None,
                'visibility_pending_pixel_audit':True},allow_nan=False)+'\n')
            frame_map.append(frame,time_s)
            captured.append(frame)
        camera.verify(captured)
        completed = True
    finally:
        def restore():
            world.apply_settings(original_settings)
            restored = world.get_settings()
            if (restored.synchronous_mode != original_settings.synchronous_mode or
                restored.fixed_delta_seconds != original_settings.fixed_delta_seconds):
                raise ValueError('Native school-bus world settings restore failed')
        close_all([(name, action) for name, action in (
            ('signal_source', signal_file.close if signal_file else None),
            ('motion_source', motion_file.close if motion_file else None),
            ('pupil_source', pupil_file.close if pupil_file else None),
            ('frame_map', frame_map.close if frame_map else None),
            ('pipeline', (lambda: pipeline.close(confirmed=completed)) if pipeline else None),
            ('cameras', camera.close if camera else None),
            *((f'encoder_{name}', sink.close) for name, sink in sinks.items()),
            *((f'actor_{index}', actor.destroy) for index, actor in enumerate(reversed(actors))),
            ('world_settings_restore', restore),
        ) if action is not None])
    sources = {}
    for name in ('motion_original.jsonl','pupil_original.jsonl','signal_command_original.jsonl','video_frames.jsonl',
                 'trace.jsonl','road.xodr',*(name+'.mkv' for name in CAMERAS)):
        path = output / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('School-bus source missing after acquisition: ' + name)
        sources[name] = _sha(path)
    inventory = {'case_id':CASE_ID,'frames':captured,'source_sha256':sources,
                 'road_id':construction['road_id'],
                 'initial_forward_separation_m':construction['initial_forward_separation_m'],
                 'heading_dot':construction['heading_dot'],
                 'undivided_road_verified':False,
                 'bus_equipment_verified':False,'pupil_purpose_verified':False,
                 'front_rear_red_visibility_verified':False,
                 'physical_acceptance_claimed':False,'legal_conclusion':None}
    with (output/'native-acquisition-inventory.json').open('x') as stream:
        json.dump(inventory,stream,indent=2,allow_nan=False);stream.write('\n')
    return inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan',required=True)
    parser.add_argument('--scene',required=True)
    parser.add_argument('--case-id',default=CASE_ID)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    scene = json.loads(Path(args.scene).read_text())
    check_plan(plan,args.case_id)
    check_scene(scene)
    if not args.check:
        if not args.output_dir:raise ValueError('Native output directory required')
        run(plan,scene,args.output_dir,host=args.host,port=args.port)


if __name__ == '__main__':
    main()
