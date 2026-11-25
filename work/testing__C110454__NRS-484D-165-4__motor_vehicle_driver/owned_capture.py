"""Operator-owned Native site, sensor and world lifecycle for parked headlamps."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from camera_recorder import CameraRecorder, PROFILE_DIMENSIONS, VIEWS, encode_original_videos
from native_capture import capture_interval


def capture_owned(client, packet_path, output_dir, *, case_id, mode,
                  transform_factory, control_factory, light_enum,
                  recorder_factory=CameraRecorder, diagnostic_fixture=False,
                  pipeline_factory=None, camera_pose_source='primary'):
    """Capture an exact original interval from a supplied reviewed site packet.

    The packet is source material, not proof that its parking and intersection
    polygons or headlamp emission are physically correct. The caller supplies
    the CARLA type factories and an existing operator-owned client.
    """
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    packet_path = Path(packet_path)
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    if (packet.get('format') != 'parked-headlamp-site-v1' or
            packet.get('case_id') != case_id or not case_id.endswith('__' + mode) or
            packet.get('diagnostic_fixture') is not diagnostic_fixture or
            packet.get('cell_id') != 'C110454' or
            packet.get('actor') != 'motor_vehicle_driver' or
            not packet.get('parking_source_ref') or
            not packet.get('intersection_source_ref')):
        raise ValueError('exact reviewed Native site identity or provenance missing')
    if set(packet.get('cameras', {})) != set(VIEWS):
        raise ValueError('four original camera constructions required')
    if camera_pose_source not in ('primary', 'fallback1'):
        raise ValueError('unknown source-reviewed camera pose selection')
    selected_cameras = packet['cameras']
    if camera_pose_source == 'fallback1':
        selected_cameras = packet.get('alternate_camera_poses')
        if (not isinstance(selected_cameras, dict) or set(selected_cameras) != set(VIEWS) or
                not packet.get('alternate_camera_pose_source_ref')):
            raise ValueError('source-reviewed alternate camera poses required')
    output = Path(output_dir)
    originals = ['actor-state.jsonl', 'camera-frame-map.jsonl', 'video_frames.jsonl',
                 'native-source-receipt.json', 'site-packet.json', 'lamp-roi.json',
                 'trace.jsonl', 'capture-seal.json']
    originals.extend(view + ext for view in VIEWS for ext in ('.zip', '.mkv'))
    if output.exists() and any((output / name).exists() for name in originals):
        raise ValueError('Native attempt already contains original acquisition')
    reviewed = dict(packet)
    reviewed['source_path'] = str(packet_path)
    reviewed['source_sha256'] = hashlib.sha256(raw).hexdigest()
    roi_raw = None
    if mode != 'unlit' and recorder_factory is CameraRecorder:
        roi_ref = packet.get('lamp_roi_source_path')
        if not isinstance(roi_ref, str) or not roi_ref:
            raise ValueError('reviewed original lamp ROI source required')
        roi_path = Path(roi_ref).resolve(strict=True)
        roi_raw = roi_path.read_bytes()
        if hashlib.sha256(roi_raw).hexdigest() != packet.get('lamp_roi_sha256'):
            raise ValueError('reviewed original lamp ROI hash differs')
    saved = snapshot(client)
    spawned = []
    pipeline = None
    completed = False
    try:
        world = client.get_world()
        settings = copy.copy(world.get_settings())
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        observed = world.get_settings()
        if observed.synchronous_mode is not True or abs(observed.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError('Native 20 Hz world settings readback differs')
        native_map = world.get_map()
        if (native_map.name != packet.get('map_name') or
                hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() != packet.get('map_sha256')):
            raise ValueError('Native map differs from reviewed site')
        library = world.get_blueprint_library()
        blueprint_id = packet.get('vehicle_blueprint_id')
        if not isinstance(blueprint_id, str) or not blueprint_id.startswith('vehicle.'):
            raise ValueError('reviewed vehicle blueprint missing')
        vehicle = world.spawn_actor(library.find(blueprint_id), transform_factory(packet['vehicle_transform']))
        if vehicle is None:
            raise ValueError('Native parked vehicle spawn failed')
        spawned.append(vehicle)
        cameras = {}
        for view in VIEWS:
            spec = selected_cameras[view]
            if spec.get('blueprint_id') != 'sensor.camera.rgb':
                raise ValueError('original camera blueprint differs')
            blueprint = library.find('sensor.camera.rgb')
            width, height = PROFILE_DIMENSIONS[view]
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('sensor_tick', '0.05')
            camera = world.spawn_actor(blueprint, transform_factory(spec), attach_to=vehicle)
            if camera is None:
                raise ValueError('Native original camera spawn failed')
            spawned.append(camera)
            cameras[view] = camera
        control = control_factory(hand_brake=True)
        if control.hand_brake is not True:
            raise ValueError('parking control readback differs')
        recorder = recorder_factory(cameras, output)
        if pipeline_factory is not None:
            pipeline = pipeline_factory(client, vehicle, output, case_id)
        receipt = capture_interval(world, vehicle, light_enum, control, recorder,
                                   reviewed, output, case_id=case_id, mode=mode,
                                   capture_after_tick=None if pipeline is None else pipeline.capture)
        if recorder_factory is CameraRecorder:
            frame_rows = [json.loads(line) for line in (output / 'video_frames.jsonl').read_text().splitlines()]
            receipt['original_camera_videos'] = encode_original_videos(output, frame_rows)
        completed = True
        output.mkdir(parents=True, exist_ok=True)
        (output / 'site-packet.json').write_bytes(raw)
        if roi_raw is not None:
            (output / 'lamp-roi.json').write_bytes(roi_raw)
        (output / 'native-source-receipt.json').write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        return receipt
    finally:
        try:
            try:
                if pipeline is not None:
                    pipeline.close(confirmed=completed)
            finally:
                for actor in reversed(spawned):
                    actor.destroy()
        finally:
            restore(client, saved)
