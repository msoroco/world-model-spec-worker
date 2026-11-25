"""Saved-source lamp-state diagnostic for NRS 484D.100(1)(c).

Native light-state readback is an equipment setting, not proof of actual photons,
class-specific legal sufficiency, device authority, or statutory compliance.
"""
from __future__ import annotations

import hashlib
import json
import math

ASSIGNMENT = 'training__C179824__NRS-484D-100-1__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def measure(raw_frames, raw_context):
    packet, context = json.loads(raw_frames), json.loads(raw_context)
    require(packet.get('assignment_id') == ASSIGNMENT and context.get('assignment_id') == ASSIGNMENT,
            'assignment mismatch')
    kind = packet.get('source_kind')
    require(kind in ('synthetic_native_sample', 'synthetic_diagnostic', 'native_saved_sample') and
            context.get('source_kind') == kind, 'source kind mismatch')
    for name in ('highway_source_sha256', 'vehicle_class_source_sha256',
                 'device_content_source_sha256', 'device_authority_source_sha256',
                 'device_placement_source_sha256', 'device_timing_source_sha256'):
        value = context.get(name)
        require(isinstance(value, str) and len(value) == 64 and
                all(c in '0123456789abcdef' for c in value), name + ' missing')
    require(context.get('state') == 'Nevada' and context.get('public_highway') is True,
            'Nevada highway source missing')
    require(context.get('vehicle_class') == 'ordinary_motor_vehicle',
            'vehicle class source missing')
    require(context.get('directive') == 'use_lamps' and context.get('device_official') is True,
            'official lamp-use directive missing')
    require(context.get('device_governs_road_id') == context.get('road_id'),
            'device does not govern roadway')
    frames = packet.get('frames')
    require(isinstance(frames, list) and len(frames) >= 600,
            'recording shorter than 30 seconds')
    require(packet.get('vehicle_id'), 'vehicle identity missing')
    before = None
    governed, headlamp_on, position_on, both_on, moving = [], [], [], [], []
    for i, row in enumerate(frames):
        t = row.get('time_s')
        require(row.get('video_frame') == i and isinstance(t, (int, float)) and
                math.isfinite(t) and abs(t - i / 20) < 1e-8,
                'noncontiguous 20 Hz frames')
        native = row.get('native_frame')
        require(type(native) is int and (before is None or native > before),
                'Native frame order missing')
        before = native
        require(row.get('vehicle_id') == packet['vehicle_id'], 'vehicle identity changed')
        cameras = row.get('camera_native_frames')
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS) and
                all(cameras[c] == native for c in CAMERAS), 'four-camera frame join missing')
        require(type(row.get('device_active')) is bool, 'device timing source missing')
        require(type(row.get('headlamp_setting_on')) is bool and
                type(row.get('position_lamp_setting_on')) is bool,
                'lamp readback missing')
        speed = row.get('speed_mps')
        require(isinstance(speed, (int, float)) and not isinstance(speed, bool) and
                math.isfinite(speed) and speed >= 0, 'vehicle speed source missing')
        require(row.get('road_id') == context['road_id'], 'vehicle left governed road')
        if row['device_active']:
            governed.append(i)
            if row['headlamp_setting_on']:
                headlamp_on.append(i)
            if row['position_lamp_setting_on']:
                position_on.append(i)
            if row['headlamp_setting_on'] and row['position_lamp_setting_on']:
                both_on.append(i)
        if speed > .1:
            moving.append(i)
    return {'format': 'nrs-484d-100-1-lamp-diagnostic-v1',
            'assignment_id': ASSIGNMENT, 'source_kind': kind,
            'frames_sha256': digest(raw_frames), 'context_sha256': digest(raw_context),
            'frame_count': len(frames), 'duration_s': len(frames) / 20,
            'governed_frames': governed, 'headlamp_setting_on_frames': headlamp_on,
            'position_lamp_setting_on_frames': position_on,
            'both_settings_on_frames': both_on, 'moving_frames': moving,
            'actual_pixels_verified': False, 'class_lamp_sufficiency_verified': False,
            'civil_night_branch_verified': False, '1000_ft_visibility_branch_verified': False,
            'parked_exception_resolved': False, 'legal_result': None}


def measure_original(raw_poses, raw_frame_map, raw_context, raw_opendrive):
    context = json.loads(raw_context)
    require(context.get('map_source_sha256') == digest(raw_opendrive),
            'OpenDRIVE source hash mismatch')
    poses = [json.loads(line) for line in raw_poses.splitlines() if line.strip()]
    mapping = [json.loads(line) for line in raw_frame_map.splitlines() if line.strip()]
    require(len(poses) == len(mapping) and bool(poses), 'original frame map length mismatch')
    for pose, row in zip(poses, mapping):
        require(all(pose.get(key) == row.get(key) for key in
                    ('video_frame', 'native_frame', 'camera_native_frames')) and
                abs(pose['time_s'] - row['time_s']) < 1e-8,
                'original frame map join mismatch')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': context.get('source_kind'),
              'vehicle_id': poses[0]['vehicle_id'], 'frames': poses}
    result = measure(json.dumps(packet, sort_keys=True, separators=(',', ':')).encode(), raw_context)
    result.update(original_pose_sha256=digest(raw_poses),
                  original_frame_map_sha256=digest(raw_frame_map),
                  original_opendrive_sha256=digest(raw_opendrive))
    return result
