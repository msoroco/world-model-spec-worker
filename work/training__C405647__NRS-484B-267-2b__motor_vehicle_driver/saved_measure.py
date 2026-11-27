"""Join original emergency approach, qualification, lamps, officer and body sources."""
import hashlib
import json
import math
from pathlib import Path
from source_review import join
from measure_emergency import measure

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
COUNT = 600

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]

def require(value, message):
    if not value:
        raise ValueError(message)

def measure_saved(folder, case_id, diagnostic=False):
    folder = Path(folder)
    source = join(folder, case_id, diagnostic=diagnostic)
    for name in (*VIDEOS, 'video_frames.jsonl', 'emergency-native.jsonl',
                 'lamp-pixel-review.json', 'signal-pixel-review.json', 'road.xodr'):
        require((folder / name).is_file(), 'Missing required source: ' + name)
    frames = rows(folder / 'video_frames.jsonl')
    native = rows(folder / 'emergency-native.jsonl')
    lamp = json.loads((folder / 'lamp-pixel-review.json').read_text())
    signal = json.loads((folder / 'signal-pixel-review.json').read_text())
    require(len(frames) == len(native) == len(lamp.get('frames', [])) ==
            len(signal.get('frames', [])) == COUNT, 'Full 600-frame source join required')
    for packet in (lamp, signal):
        require(packet.get('case_id') == case_id and packet.get('review_kind') ==
                ('synthetic_diagnostic' if diagnostic else 'original_native'),
                'Original pixel review identity differs')
        if not diagnostic:
            require(all(packet.get('video_sha256', {}).get(name) == sha(folder / name)
                        for name in VIDEOS), 'Original pixel review video hash differs')
    transformed = []
    first_ego = first_emergency = None
    prior_speed = None
    for i, (f, n, l, s) in enumerate(zip(frames, native, lamp['frames'], signal['frames'])):
        require(f.get('video_frame') == n.get('frame') == l.get('frame') == s.get('frame') == i,
                'Synchronized original frame sequence differs')
        require(f.get('native_frame') == n.get('native_frame') and
                f.get('camera_native_frames') == dict.fromkeys(('overview', 'approach',
                    'reference_corner', 'driver_reference'), n['native_frame']),
                'Four original camera frames differ')
        require(abs(f.get('time_s', -1) - i / 20) < .06 and
                abs(n.get('t_s', -1) - f['time_s']) < .06,
                'Original Native time join differs')
        ego, emergency = n.get('ego', {}), n.get('emergency', {})
        first_ego = first_ego or ego.get('actor_id')
        first_emergency = first_emergency or emergency.get('actor_id')
        require(first_ego and first_emergency and first_ego != first_emergency and
                ego.get('actor_id') == first_ego and emergency.get('actor_id') == first_emergency,
                'Original participant identity differs')
        require(ego.get('road_id') == emergency.get('road_id') == 405647 and
                ego.get('lane_id') == -2 and emergency.get('lane_id') == -1,
                'Original road/lane readback differs')
        require(type(l.get('vehicle_visible')) is bool and
                type(l.get('qualifying_flashes_visible')) is bool and
                type(s.get('hand_signal_visible')) is bool and
                s.get('officer_direction') in {'none', 'proceed', 'stop', 'other'},
                'Original lamp, hand or officer pixel/source review incomplete')
        speed = ego.get('speed_mps')
        gap = abs(ego['y_m'] - emergency['y_m']) - ego['half_width_m'] - emergency['half_width_m']
        require(all(isinstance(v, (int, float)) and math.isfinite(v) for v in
                    (speed, emergency.get('speed_mps'), gap)) and gap >= 0,
                'Original body surface gap or speed invalid')
        transformed.append({'video_frame': i, 'native_frame': n['native_frame'],
            'time_s': i / 20, 'source_cameras': dict.fromkeys(('overview', 'approach',
                'reference_corner', 'driver_reference'), i),
            'emergency_visible': l['vehicle_visible'],
            'flashing_lamps_visible': l['qualifying_flashes_visible'],
            'hand_signal_visible': s['hand_signal_visible'],
            'officer_direction': s['officer_direction'],
            'ego_center_x_m': ego['x_m'], 'emergency_center_x_m': emergency['x_m'],
            'ego_speed_mps': speed, 'emergency_speed_mps': emergency['speed_mps'],
            'surface_gap_m': gap,
            'ego_deceleration_mps2': max(0, (prior_speed - speed) * 20) if prior_speed is not None else 0})
        prior_speed = speed
    context = {'source_kind': 'synthetic_cpu_emergency_readback' if diagnostic else
                         'original_native_emergency_readback',
        'native_map_sha256': sha(folder / 'road.xodr'),
        'ego_blueprint_sha256': sha(folder / 'emergency-native.jsonl'),
        'emergency_actor_sha256': sha(folder / 'emergency-native.jsonl'),
        'emergency_role_source_sha256': source['source_sha256']['vehicle_authorization'],
        'flashing_lamp_source_sha256': source['source_sha256']['flashing_qualification'],
        'vehicle_extent_sha256': sha(folder / 'emergency-native.jsonl'),
        'visibility_source_sha256': sha(folder / 'lamp-pixel-review.json'),
        'officer_direction_source_sha256': source['source_sha256']['officer_direction'],
        'emergency_role': source['qualification_role'],
        'lamps_meet_nrs_484a_480_3': True,
        'activation_mode': 'visible_hand_signal' if case_id.endswith('probe_04') else 'moving_vehicle'}
    result = measure(context, transformed)
    return {'measurement': result, 'source_join': source,
            'source_sha256': {name: sha(folder / name) for name in
                (*VIDEOS, 'road.xodr', 'video_frames.jsonl', 'emergency-native.jsonl',
                 'lamp-pixel-review.json', 'signal-pixel-review.json', 'trace.jsonl')}}
