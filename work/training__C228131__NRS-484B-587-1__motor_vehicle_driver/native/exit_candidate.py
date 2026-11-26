"""Unselected C62507 exit-road construction and saved meter proposal.

The original C228131 cell is enter_road. This module does not select an exit
case or claim actor eligibility for the unallocated C62507 catalog cell.
"""
import hashlib
import json
import math

FRAMES = 600
RATE_HZ = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
EXIT_X_M = {'indicated_exit': 0.0, 'outside_exit': 60.0}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def finite(value, reason):
    require(type(value) in (int, float) and math.isfinite(value), reason)
    return float(value)


def target(mode, frame):
    require(mode in EXIT_X_M and type(frame) is int and 0 <= frame < FRAMES,
            'Unknown controlled-exit target')
    progress = min(1.0, (frame / RATE_HZ) / 24)
    crossing_x = EXIT_X_M[mode]
    # A 1 m half-width footprint first leaves the highway when the center
    # passes y=-2.5 m relative to the authored edge at y=-3.5 m.
    return {'x_m': crossing_x - 40 * (2.5 / 9) + 40 * progress,
            'y_m': -progress * 9,
            'target_speed_mps': 2.0,
            'requested_crossing_x_m': crossing_x,
            'reference_frame': 'authored highway to frontage road',
            'requested_direction': 'from_highway'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rows(raw):
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def measure(poses_raw, frames_raw, context_raw, road_raw):
    """Find original footprint leave events without deciding the legal outcome."""
    context = json.loads(context_raw)
    require(context.get('source_kind') in ('synthetic_cpu', 'original_native'),
            'Original or declared diagnostic source kind missing')
    require(context.get('road_source_sha256') == sha(road_raw),
            'Exit road source hash differs')
    for key in ('controlled_access_designation_sha256',
                'official_device_authority_sha256', 'device_content_sha256',
                'device_erection_sha256', 'exit_extent_source_sha256'):
        value = context.get(key)
        require(isinstance(value, str) and len(value) == 64 and
                all(ch in '0123456789abcdef' for ch in value), key + ' missing')
    require(context.get('controlled_access_highway') is True and
            context.get('device_official') is True and
            context.get('device_erected') is True and
            context.get('device_indicates_exit') is True,
            'Controlled-access and official indicated exit source missing')
    gate = context.get('indicated_exit_x_interval_m')
    require(isinstance(gate, list) and len(gate) == 2,
            'Indicated exit extent missing')
    lo, hi = (finite(value, 'Indicated exit extent missing') for value in gate)
    require(lo < hi, 'Indicated exit extent differs')
    edge = finite(context.get('highway_edge_y_m'), 'Highway edge missing')
    poses, frames = rows(poses_raw), rows(frames_raw)
    require(len(poses) == len(frames) == FRAMES,
            '30-second original exit coverage missing')
    previous_inside = None
    previous_native = None
    events = []
    for index, (pose, frame) in enumerate(zip(poses, frames)):
        native = pose.get('native_frame')
        time_s = finite(pose.get('time_s'), 'Exit pose time missing')
        require(pose.get('video_frame') == frame.get('video_frame') == index
                and native == frame.get('native_frame') and type(native) is int
                and (previous_native is None or native > previous_native)
                and abs(time_s - index / RATE_HZ) < 1e-8
                and abs(time_s - finite(frame.get('time_s'), 'Exit frame time missing')) < 1e-8,
                'Exit pose/frame join differs')
        previous_native = native
        cameras = pose.get('camera_native_frames')
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS)
                and cameras == frame.get('camera_native_frames')
                and all(cameras[name] == native for name in CAMERAS),
                'Four original exit camera joins missing')
        require(pose.get('vehicle_id') == poses[0].get('vehicle_id') and
                pose.get('vehicle_id'), 'Exit vehicle identity differs')
        center = pose.get('center_xy_m')
        require(isinstance(center, list) and len(center) == 2,
                'Exit vehicle center missing')
        x, y = (finite(value, 'Exit vehicle center missing') for value in center)
        half_width = finite(pose.get('footprint_half_width_m'),
                            'Exit vehicle footprint missing')
        require(half_width > 0, 'Exit vehicle footprint missing')
        inside = y - half_width >= edge
        if previous_inside is True and inside is False:
            events.append({'video_frame': index, 'native_frame': native,
                           'time_s': time_s, 'measured_center_x_m': x,
                           'within_indicated_exit': lo <= x <= hi})
        previous_inside = inside
    require(len(events) == 1, 'Exactly one measured exit event required')
    return {'format': 'nrs-484b-587-1-saved-exit-facts-v1',
            'source_kind': context['source_kind'],
            'pose_sha256': sha(poses_raw), 'frame_map_sha256': sha(frames_raw),
            'context_sha256': sha(context_raw), 'road_sha256': sha(road_raw),
            'frame_count': FRAMES, 'duration_s': FRAMES / RATE_HZ,
            'four_camera_joins': FRAMES * len(CAMERAS),
            'exit_events': events,
            'official_device_authority_independently_reviewed': False,
            'legal_result': None, 'physical_completion_verified': False}
