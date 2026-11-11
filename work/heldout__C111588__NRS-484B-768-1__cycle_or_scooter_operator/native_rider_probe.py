"""Native bicycle/attached-walker arm-signal construction probe.

This is an unverified physical mechanism. Saved RGB review must confirm whether
the rider and one-frame arm pose are actually visible and meaningful.
"""

import argparse
import json
from pathlib import Path

from rider_arm import RiderArm
from rider_camera import CAMERAS, LosslessSourceSink, RiderCameraCapture
from rider_route import control, select_left_turn


CASE_ID = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__bicycle_signal_once'


def check_config(config):
    if config.get('selected_case_id') != CASE_ID:
        raise ValueError('Wrong exact rider probe case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-768-1', 'C111588', 'cycle_or_scooter_operator'):
        raise ValueError('Wrong rider law/cell/actor')
    if config.get('rate_hz') != 20 or config.get('frames') != 200 or config.get('signal_frame_index') != 35:
        raise ValueError('Rider rate, duration or single signal event differs')
    if config.get('construction_probe_only') is not True:
        raise ValueError('Rider probe cannot masquerade as delivery')


def _control(bicycle, waypoint):
    transform = bicycle.get_transform()
    p, h, v = transform.location, transform.get_forward_vector(), bicycle.get_velocity()
    target = waypoint.transform.location
    return control([p.x, p.y], [h.x, h.y], [v.x, v.y],
                   [target.x, target.y])


def run(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap

    check_config(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    original = world.get_settings()
    actors = []
    pipeline = frame_map = cameras = motion = bone_rows = None
    sinks = {}
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        route = select_left_turn(world.get_map())
        library = world.get_blueprint_library()
        bicycle_blueprint = library.find('vehicle.bh.crossbike')
        if bicycle_blueprint.get_attribute('base_type').as_str() != 'bicycle':
            raise ValueError('Native selected actor is not a bicycle blueprint')
        bicycle = world.try_spawn_actor(bicycle_blueprint, route[0].transform)
        if bicycle is None:
            raise ValueError('Native bicycle spawn failed')
        actors.append(bicycle)
        walker_blueprint = library.filter('walker.pedestrian.*')[0]
        rider = world.try_spawn_actor(
            walker_blueprint,
            carla.Transform(carla.Location(z=.65)),
            attach_to=bicycle, attachment_type=carla.AttachmentType.Rigid)
        if rider is None:
            raise ValueError('Native attached rider spawn failed')
        actors.append(rider)
        arm = RiderArm(rider, carla)
        arm.set_signal(False)
        pipeline = PipelineCapture(client, bicycle, output, CASE_ID,
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        motion = (output / 'rider_motion.jsonl').open('x')
        bone_rows = (output / 'rider_arm_bones.jsonl').open('x')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = RiderCameraCapture(world, carla, bicycle, sinks)
        (output / 'rider_context.json').write_text(json.dumps({
            'rider_id': str(rider.id), 'device_type': 'bicycle',
            'device_type_source': 'Native vehicle.bh.crossbike blueprint base_type readback',
            'on_roadway': True,
            'roadway_source': 'selected connected Native roadway waypoints; actual occupancy review pending',
            'designated_turn_lane': {'value': None, 'source_ref': None},
            'both_hands_required_for_safety': {'value': None, 'source_ref': None}},
            indent=2) + '\n')
        frames = []
        start = None
        for index in range(config['frames']):
            arm.set_signal(index == config['signal_frame_index'])
            target = route[min(3 + index // 6, len(route) - 1)]
            bicycle.apply_control(carla.VehicleControl(**_control(bicycle, target)))
            frame = world.tick()
            cameras.wait_for_frame(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native rider snapshot/frame differs')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            trace = pipeline.capture(frame, time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Native rider trace/frame differs')
            motion.write(json.dumps({'frame': frame, 'time_s': time_s,
                                     'rider_id': str(rider.id),
                                     'rider_yaw_deg': bicycle.get_transform().rotation.yaw}) + '\n')
            bone_rows.write(json.dumps({'frame': frame, 'time_s': time_s,
                                        'rider_id': str(rider.id),
                                        **arm.readback()}) + '\n')
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        (output / 'construction-probe.json').write_text(json.dumps({
            'format': 'worker-rider-construction-probe',
            'case_id': CASE_ID, 'map_name': world.get_map().name,
            'bicycle_blueprint': bicycle.type_id,
            'rider_blueprint': rider.type_id,
            'arm_bone': 'crl_arm__L', 'commanded_signal_frame_index': 35,
            'frames': frames, 'visible_signal_verified': False,
            'turn_completed_verified': False, 'delivery_ready': False}, indent=2) + '\n')
    finally:
        if motion is not None:
            motion.close()
        if bone_rows is not None:
            bone_rows.close()
        if frame_map is not None:
            frame_map.close()
        if pipeline is not None:
            pipeline.close(confirmed=False)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Native rider world settings restore failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--config', default='probe-config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    check_config(config)
    if args.output_dir:
        run(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
