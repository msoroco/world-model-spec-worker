"""Measure a controlled-access entry event from retained saved source bytes."""
import hashlib
import json
import math

ASSIGNMENT = 'training__C228131__NRS-484B-587-1__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'indicated_gate', 'highway_side')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def finite(value, reason):
    require(type(value) in (int, float) and math.isfinite(value), reason)
    return float(value)


def parse_lines(raw):
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def measure(pose_bytes, frame_map_bytes, context_bytes, road_bytes):
    context = json.loads(context_bytes)
    require(context.get('assignment_id') == ASSIGNMENT,
            'assignment identity differs')
    require(context.get('source_kind') in ('synthetic_cpu', 'original_native'),
            'source provenance differs')
    require(context.get('road_source_sha256') == sha(road_bytes),
            'road source hash differs')
    for key in ('controlled_access_designation_sha256', 'official_device_authority_sha256',
                'device_content_sha256', 'device_erection_sha256',
                'entrance_extent_source_sha256'):
        value = context.get(key)
        require(isinstance(value, str) and len(value) == 64
                and all(c in '0123456789abcdef' for c in value), key + ' missing')
    require(context.get('controlled_access_highway') is True
            and context.get('device_official') is True
            and context.get('device_erected') is True
            and context.get('device_indicates_entry') is True,
            'controlled-access and official indicated entry sources missing')
    road_id = context.get('highway_road_id')
    require(road_id, 'highway identity missing')
    edge_y = finite(context.get('highway_edge_y_m'), 'highway edge missing')
    gate = context.get('indicated_entrance_x_interval_m')
    require(isinstance(gate, list) and len(gate) == 2, 'indicated gate missing')
    lo, hi = (finite(x, 'indicated gate missing') for x in gate)
    require(lo < hi, 'indicated gate interval differs')
    poses = parse_lines(pose_bytes)
    mapped = parse_lines(frame_map_bytes)
    require(len(poses) == len(mapped) >= 600, '30-second retained source coverage missing')
    first_frame = None
    previous_inside = False
    previous_native = None
    events = []
    for index, (pose, frame) in enumerate(zip(poses, mapped)):
        native = pose.get('native_frame')
        time_s = finite(pose.get('time_s'), 'pose time missing')
        require(pose.get('video_frame') == frame.get('video_frame') == index
                and native == frame.get('native_frame')
                and type(native) is int
                and (previous_native is None or native > previous_native)
                and abs(time_s - index / 20) < 1e-8
                and abs(time_s - finite(frame.get('time_s'), 'frame time missing')) < 1e-8,
                'retained pose/frame-map join differs')
        previous_native = native
        if first_frame is None:
            first_frame = native
        cameras = pose.get('camera_native_frames')
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS)
                and cameras == frame.get('camera_native_frames')
                and all(cameras[name] == native for name in CAMERAS),
                'four original camera frame joins missing')
        require(pose.get('vehicle_id') == poses[0].get('vehicle_id')
                and pose.get('vehicle_id'), 'vehicle identity differs')
        center = pose.get('center_xy_m')
        require(isinstance(center, list) and len(center) == 2,
                'measured vehicle center missing')
        x, y = (finite(v, 'measured vehicle center missing') for v in center)
        half_width = finite(pose.get('footprint_half_width_m'), 'measured footprint missing')
        require(half_width > 0, 'measured footprint missing')
        inside = y - half_width >= edge_y
        if inside and not previous_inside:
            events.append({'video_frame': index, 'native_frame': native, 'time_s': time_s,
                           'measured_center_x_m': x,
                           'within_indicated_gate': lo <= x <= hi})
        previous_inside = inside
    require(len(events) == 1, 'exactly one measured entry event required')
    return {'format': 'nrs-484b-587-1-saved-entry-facts-v1',
            'assignment_id': ASSIGNMENT, 'source_kind': context.get('source_kind'),
            'pose_sha256': sha(pose_bytes), 'frame_map_sha256': sha(frame_map_bytes),
            'context_sha256': sha(context_bytes), 'road_sha256': sha(road_bytes),
            'frame_count': len(poses), 'duration_s': len(poses) / 20,
            'four_camera_joins': len(poses) * len(CAMERAS),
            'highway_road_id': road_id, 'entry_events': events,
            'official_device_authority_independently_reviewed': False,
            'legal_result': None, 'physical_completion_verified': False}
