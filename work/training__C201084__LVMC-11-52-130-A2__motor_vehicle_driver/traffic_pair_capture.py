"""Original-source optional-lead traffic pair; no statutory verdict."""
import copy
import json
import queue
from pathlib import Path

from traffic_pair_controller import apply as apply_pair
from fire_lane_survey import CAMERAS, require
from native_capture import (CAMERA_SPECS, FFV1Sink, OriginalFrameMap,
                            install_cameras, sample_native)


def sample_lead(world, carla, lead, plan):
    transform = lead.get_transform()
    location = transform.location
    waypoint = world.get_map().get_waypoint(
        location, project_to_road=True, lane_type=carla.LaneType.Driving)
    require(waypoint is not None and
            waypoint.road_id == plan['fixed_context']['road_id'],
            'Original lead vehicle departed surveyed road')
    vertices = lead.bounding_box.get_world_vertices(transform)
    require(len(vertices) >= 4, 'Original lead vehicle body unavailable')
    velocity = lead.get_velocity()
    return {'lead_actor_id': lead.id, 'lead_road_id': waypoint.road_id,
            'lead_lane_id': waypoint.lane_id,
            'lead_pose_xyz_m': [location.x, location.y, location.z],
            'lead_yaw_deg': transform.rotation.yaw,
            'lead_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'lead_body_vertices_xyz_m': [[v.x, v.y, v.z] for v in vertices]}


def acquire(world, carla, ego, follower, lead, sign, plan, attempt,
            *, sink_factory=FFV1Sink, camera_installer=install_cameras,
            frame_map_factory=OriginalFrameMap, timeout_s=10):
    require(plan['capture_hz'] == 20 and plan['capture_frames'] >= 600 and
            plan['camera_names'] == list(CAMERAS),
            'Original traffic-pair capture contract differs')
    require(plan['traffic_pair']['lead_present'] is (lead is not None),
            'Traffic-pair lead presence differs from surveyed plan')
    settings = world.get_settings()
    require(settings.synchronous_mode and settings.fixed_delta_seconds == 0.05,
            'Original world must be synchronous at 20 Hz')
    attempt = Path(attempt)
    attempt.mkdir(parents=True, exist_ok=True)
    originals = ('native-actors.jsonl', 'video_frames.jsonl',
                 *(name+'.mkv' for name in CAMERAS))
    require(not any((attempt/name).exists() for name in originals),
            'Retain prior originals; use a fresh attempt')
    queues = {name: queue.Queue() for name in CAMERAS}
    sensors, sinks, frames, rows = [], {}, None, None
    previous_frame, first_elapsed = -1, None
    tuning = plan.get('traffic_pair_controller_tuning') or {}
    destination = plan['traffic_pair']['destination_xy_m']
    try:
        sensors = camera_installer(world, carla, ego,
                                   lambda name, image: queues[name].put(image))
        for name, width, height, *_ in CAMERA_SPECS:
            sinks[name] = sink_factory(attempt/(name+'.mkv'), width, height)
        frames = frame_map_factory(attempt/'video_frames.jsonl')
        rows = (attempt/'native-actors.jsonl').open('x', encoding='utf-8')
        for index in range(plan['capture_frames']):
            requested = apply_pair(ego, lead, carla, destination, **tuning)
            if lead is not None:
                lead.apply_control(carla.VehicleControl(
                    throttle=0.0, brake=1.0, steer=0.0, hand_brake=True))
            follower.apply_control(carla.VehicleControl(
                throttle=0.0, brake=1.0, steer=0.0, hand_brake=False))
            native_frame = world.tick()
            require(type(native_frame) is int and native_frame > previous_frame,
                    'Original CARLA world frame did not advance')
            previous_frame = native_frame
            for name in CAMERAS:
                image = queues[name].get(timeout=timeout_s)
                require(image.frame == native_frame,
                        'Original camera frame join differs: '+name)
                sinks[name].write(image)
            elapsed = world.get_snapshot().timestamp.elapsed_seconds
            if first_elapsed is None:
                first_elapsed = elapsed
            frames.append(native_frame, elapsed-first_elapsed)
            observed = sample_native(world, carla, ego, follower, sign, plan)
            if lead is not None:
                observed.update(sample_lead(world, carla, lead, plan))
            observed.update(lead_present=lead is not None,
                            frame=native_frame, video_frame=index,
                            requested_control=requested,
                            physical_completion_claimed=False,
                            statutory_necessity_claimed=False)
            rows.write(json.dumps(observed, allow_nan=False)+'\n')
    finally:
        if rows is not None:
            rows.close()
        if frames is not None:
            frames.close()
        for sensor in reversed(sensors):
            sensor.stop()
            sensor.destroy()
        errors = []
        for sink in sinks.values():
            try:
                sink.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise errors[0]
    return {'source_frames': plan['capture_frames'],
            'camera_paths': [name+'.mkv' for name in CAMERAS],
            'frame_map': 'video_frames.jsonl', 'actors': 'native-actors.jsonl',
            'physical_completion_claimed': False,
            'statutory_necessity_claimed': False}


def acquire_with_world_restore(world, *args, **kwargs):
    previous = world.get_settings()
    configured = copy.copy(previous)
    configured.synchronous_mode = True
    configured.fixed_delta_seconds = 0.05
    world.apply_settings(configured)
    try:
        result = acquire(world, *args, **kwargs)
    finally:
        world.apply_settings(previous)
    restored = world.get_settings()
    require(restored.synchronous_mode == previous.synchronous_mode and
            restored.fixed_delta_seconds == previous.fixed_delta_seconds,
            'Original world timing was not restored')
    result['restoration_verified'] = True
    return result
