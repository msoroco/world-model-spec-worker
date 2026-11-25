"""Source-bound factual reducer for left-side one-way standing/parking.

An engineering speed tolerance identifies rest candidates; it is not a legal
definition. Official device authority, legal standing and compliance remain open.
"""
import hashlib
import json
import math

ASSIGNMENT = 'training__C150129__NRS-484B-497__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def number(value, reason):
    require(type(value) in (int, float) and math.isfinite(value), reason)
    return float(value)


def xy(value, reason):
    require(isinstance(value, list) and len(value) == 2, reason)
    return number(value[0], reason), number(value[1], reason)


def measure(raw_packet, raw_context):
    packet, context = json.loads(raw_packet), json.loads(raw_context)
    kind = packet.get('source_kind')
    require(packet.get('assignment_id') == context.get('assignment_id') == ASSIGNMENT
            and kind in ('synthetic_native_sample', 'native_saved_sample')
            and context.get('source_kind') == kind, 'assignment/source kind differs')
    for name in ('map_source_sha256', 'one_way_designation_source_sha256',
                 'street_boundary_source_sha256', 'device_inventory_source_sha256'):
        value = context.get(name)
        require(isinstance(value, str) and len(value) == 64
                and all(c in '0123456789abcdef' for c in value), name + ' missing')
    require(context.get('roadway_is_laned') is True
            and context.get('roadway_is_one_way') is True,
            'laned one-way roadway source missing')
    permission = context.get('permission_device_present')
    require(type(permission) is bool, 'permission device inventory missing')
    if permission:
        for name in ('device_authority_source_sha256', 'device_content_source_sha256',
                     'device_erection_source_sha256', 'device_governance_source_sha256'):
            value = context.get(name)
            require(isinstance(value, str) and len(value) == 64
                    and all(c in '0123456789abcdef' for c in value), name + ' missing')
        require(context.get('device_official') is True
                and context.get('device_erected') is True
                and context.get('notice_permits_left_standing_or_parking') is True
                and context.get('device_governs_road_id') == context.get('road_id'),
                'official governing permission device source missing')
    else:
        require(context.get('device_official') is False
                and context.get('device_erected') is False
                and context.get('notice_permits_left_standing_or_parking') is False,
                'absent permission device inventory differs')
    origin = xy(context.get('centerline_origin_xy_m'), 'centerline origin missing')
    direction = xy(context.get('permitted_direction_xy'), 'permitted direction missing')
    require(abs(math.hypot(*direction) - 1) < 1e-6, 'direction must be unit length')
    half_width = number(context.get('street_half_width_m'), 'street width missing')
    require(half_width > 0, 'street width missing')
    frames = packet.get('frames')
    require(isinstance(frames, list) and len(frames) >= 600,
            'recording shorter than 30 seconds')
    require(packet.get('vehicle_id'), 'vehicle identity missing')
    rest, left, other = [], [], []
    previous_native = None
    for index, row in enumerate(frames):
        require(row.get('video_frame') == index
                and abs(number(row.get('time_s'), 'timestamp missing') - index / 20) < 1e-8,
                'noncontiguous 20 Hz frames')
        native = row.get('native_frame')
        require(type(native) is int and (previous_native is None or native > previous_native),
                'Native frame order missing')
        previous_native = native
        require(row.get('vehicle_id') == packet['vehicle_id'], 'vehicle identity changed')
        cameras = row.get('camera_native_frames')
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS)
                and all(cameras[name] == native for name in CAMERAS),
                'four-camera frame join missing')
        speed = number(row.get('speed_mps'), 'speed source missing')
        require(speed >= 0, 'speed source missing')
        corners = row.get('footprint_corners_xy_m')
        require(isinstance(corners, list) and len(corners) == 4,
                'vehicle footprint missing')
        projections = []
        for corner in corners:
            x, y = xy(corner, 'vehicle footprint missing')
            dx, dy = x - origin[0], y - origin[1]
            across = direction[0] * dy - direction[1] * dx
            require(abs(across) <= half_width, 'vehicle outside sourced street boundary')
            projections.append(across)
        if speed <= .1:
            rest.append(index)
            (left if min(projections) > 0 else other).append(index)
    return {'format': 'nrs-484b-497-saved-facts-v1',
            'assignment_id': ASSIGNMENT, 'source_kind': kind,
            'packet_sha256': sha(raw_packet), 'context_sha256': sha(raw_context),
            'frame_count': len(frames), 'duration_s': len(frames) / 20,
            'rest_candidate_frames': rest, 'fully_left_rest_candidate_frames': left,
            'other_rest_candidate_frames': other,
            'permission_device_sourced': permission, 'device_id': context.get('device_id'),
            'legal_result': None, 'physical_completion_verified': False,
            'unresolved': ['legal one-way designation and official device authority require original sources',
                           'standing or parking purpose and actual camera pixels require review',
                           'physical completion and legal verdict are unverified']}


def measure_original(raw_poses, raw_frame_map, raw_context, raw_opendrive):
    context = json.loads(raw_context)
    require(context.get('map_source_sha256') == sha(raw_opendrive),
            'OpenDRIVE source hash mismatch')
    poses = [json.loads(line) for line in raw_poses.splitlines() if line.strip()]
    mapped = [json.loads(line) for line in raw_frame_map.splitlines() if line.strip()]
    require(len(poses) == len(mapped) and poses, 'original frame map length differs')
    for pose, frame in zip(poses, mapped):
        require(all(pose.get(key) == frame.get(key) for key in
                    ('video_frame', 'native_frame', 'camera_native_frames'))
                and abs(pose['time_s'] - frame['time_s']) < 1e-8,
                'original frame map join differs')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': 'native_saved_sample',
              'vehicle_id': poses[0]['vehicle_id'], 'frames': poses}
    result = measure(json.dumps(packet, sort_keys=True).encode(), raw_context)
    result['original_pose_sha256'] = sha(raw_poses)
    result['original_frame_map_sha256'] = sha(raw_frame_map)
    result['original_opendrive_sha256'] = sha(raw_opendrive)
    return result
